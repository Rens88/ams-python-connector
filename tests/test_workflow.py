from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
import warnings
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ams_smartabase.client import OperationExecution
from ams_smartabase.diagnostics import AMSEventIdUnavailableError, AMSResponseShapeError
from ams_smartabase.payloads import build_delete_payloads, build_event_import_payloads
from ams_smartabase.workflow import (
    EventCountResult,
    build_event_write_targets,
    count_event_entries,
    load_example_event_workflow_input,
    plan_event_deletions,
    require_exact_event_ids,
    run_event_delete_workflow,
    run_event_replace_workflow,
    run_event_replay_workflow,
)


class ReplayClient:
    def __init__(self, target, *, sandbox=True):
        package = build_event_import_payloads(target.records, form=target.form, mode="insert")
        self.events = []
        self.next_event_id = 1000
        self.insert_calls = 0
        url = "https://teamnl.smartabase.nl/sandbox/" if sandbox else "https://teamnl.smartabase.nl/live/"
        self.credentials = SimpleNamespace(url=url)
        for event in package.body["events"]:
            stored = dict(event)
            stored["eventId"] = self.next_event_id
            self.next_event_id += 1
            self.events.append(stored)

    def get_event(self, *, form, user_ids, date_range, time_range=("12:00 am", "11:59 pm"), data_filters=None, events_per_user=None):
        start = datetime.strptime(date_range[0], "%d/%m/%Y").date()
        finish = datetime.strptime(date_range[1], "%d/%m/%Y").date()
        matched = []
        for event in self.events:
            event_user_id = int(event["userId"]["userId"])
            event_date = datetime.strptime(event["startDate"], "%d/%m/%Y").date()
            if event["formName"] != form:
                continue
            if event_user_id not in user_ids:
                continue
            if event_date < start or event_date > finish:
                continue
            matched.append(event)
        return {"events": matched}

    def delete_event(self, event_ids, *, dry_run=True, confirm=False):
        package = build_delete_payloads(event_ids)
        if dry_run:
            return OperationExecution(
                endpoint=package.endpoint,
                attempted_count=package.attempted_count,
                dry_run=True,
                executed=False,
                body=package.body,
                row_operations=package.row_operations,
                responses=[],
            )
        if not confirm:
            raise ValueError("confirm=True is required when dry_run=False.")
        event_ids_set = {int(value) for value in event_ids}
        self.events = [event for event in self.events if int(event["eventId"]) not in event_ids_set]
        return OperationExecution(
            endpoint=package.endpoint,
            attempted_count=package.attempted_count,
            dry_run=False,
            executed=True,
            body=package.body,
            row_operations=package.row_operations,
            responses=[{"status": "ok", "eventId": int(value)} for value in event_ids],
        )

    def insert_event(self, records, *, form=None, entered_by_user_id=None, dry_run=True, confirm=False):
        self.insert_calls += 1
        package = build_event_import_payloads(
            records,
            form=form,
            mode="insert",
            entered_by_user_id=entered_by_user_id,
        )
        if dry_run:
            return OperationExecution(
                endpoint=package.endpoint,
                attempted_count=package.attempted_count,
                dry_run=True,
                executed=False,
                body=package.body,
                row_operations=package.row_operations,
                responses=[],
            )
        if not confirm:
            raise ValueError("confirm=True is required when dry_run=False.")
        for event in package.body["events"]:
            stored = dict(event)
            stored["eventId"] = self.next_event_id
            self.next_event_id += 1
            self.events.append(stored)
        return OperationExecution(
            endpoint=package.endpoint,
            attempted_count=package.attempted_count,
            dry_run=False,
            executed=True,
            body=package.body,
            row_operations=package.row_operations,
            responses=[{"status": "ok", "inserted": package.attempted_count}],
        )


class StaticEventClient:
    def __init__(self, payload):
        self.payload = payload

    def get_event(
        self,
        *,
        form,
        user_ids,
        date_range,
        time_range=("12:00 am", "11:59 pm"),
        data_filters=None,
        events_per_user=None,
    ):
        return self.payload


class WorkflowTests(unittest.TestCase):
    def test_build_event_write_targets_groups_records_by_form_and_user(self):
        records = [
            {"form": "Wellness", "user_id": 1, "about": "Ada Lovelace", "start_date": "01/05/2026", "Score": 1},
            {"form": "Wellness", "user_id": 1, "about": "Ada Lovelace", "start_date": "03/05/2026", "Score": 2},
            {"form": "Recovery", "user_id": 2, "start_date": "02/05/2026", "Score": 3},
        ]

        targets = build_event_write_targets(records)

        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0].form, "Recovery")
        self.assertEqual(targets[0].user_id, 2)
        self.assertEqual(targets[0].date_range, ("02/05/2026", "02/05/2026"))
        self.assertEqual(targets[1].form, "Wellness")
        self.assertEqual(targets[1].user_id, 1)
        self.assertEqual(targets[1].date_range, ("01/05/2026", "03/05/2026"))
        self.assertEqual(targets[1].about, "Ada Lovelace")

    def test_count_event_entries_extracts_ids_from_realistic_eventsearch_payload(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)

        result = count_event_entries(client, form=target.form, user_id=target.user_id, date_range=target.date_range)

        self.assertEqual(result.entry_count, target.expected_upload_count)
        self.assertEqual(len(result.event_ids), target.expected_upload_count)
        self.assertTrue(all(isinstance(value, int) for value in result.event_ids))

    def test_count_event_entries_extracts_ids_from_nested_result_batches(self):
        client = StaticEventClient(
            {
                "results": [
                    {
                        "search": {"form": "Synthetic Wellness"},
                        "results": [
                            {
                                "eventId": 101,
                                "rows": [{"row": 0, "pairs": [{"key": "Score", "value": "5"}]}],
                            },
                            {
                                "eventId": 102,
                                "rows": [{"row": 0, "pairs": [{"key": "Score", "value": "6"}]}],
                            },
                        ],
                    }
                ]
            }
        )

        result = count_event_entries(
            client,
            form="Synthetic Wellness",
            user_id=1,
            date_range=("01/05/2026", "02/05/2026"),
        )

        self.assertEqual(result.entry_count, 2)
        self.assertEqual(result.event_ids, [101, 102])
        self.assertEqual([row["Score"] for row in result.rows], ["5", "6"])

    def test_count_event_entries_rejects_lossy_or_nonpositive_event_ids(self):
        for value in (True, 1.9, 0, -1, "1.9", "+1"):
            with self.subTest(value=value):
                result = count_event_entries(
                    StaticEventClient({"events": [{"eventId": value}]}),
                    form="Synthetic Wellness",
                    user_id=1,
                    date_range=("01/05/2026", "01/05/2026"),
                )
                self.assertEqual(result.entry_count, 1)
                self.assertEqual(result.event_ids, [])

        generic = count_event_entries(
            StaticEventClient({"events": [{"id": 7, "formName": "Synthetic Wellness"}]}),
            form="Synthetic Wellness",
            user_id=1,
            date_range=("01/05/2026", "01/05/2026"),
        )
        self.assertEqual(generic.entry_count, 1)
        self.assertEqual(generic.event_ids, [])

    def test_exact_event_id_requirement_rejects_generic_id_without_deleting(self):
        result = count_event_entries(
            StaticEventClient(
                {"events": [{"id": 7, "athleteId": 1, "formName": "Synthetic Wellness"}]}
            ),
            form="Synthetic Wellness",
            user_id=1,
            date_range=("01/05/2026", "01/05/2026"),
        )

        with self.assertRaises(AMSEventIdUnavailableError) as raised:
            require_exact_event_ids(result)

        self.assertEqual(raised.exception.code, "exact_event_id_unavailable")
        self.assertFalse(raised.exception.request_sent)
        self.assertIn("athleteId", raised.exception.details["returned_id_like_fields"])
        self.assertIn("No deletion request was sent", str(raised.exception))

    def test_exact_event_id_requirement_rejects_unrecognized_response_shape(self):
        result = EventCountResult(
            form="Synthetic Wellness",
            user_id=1,
            date_range=("01/05/2026", "01/05/2026"),
            entry_count=1,
            event_ids=[],
            rows=[],
            raw_payload={"events": [{"eventId": 7}, {"results": []}]},
        )

        with self.assertRaises(AMSResponseShapeError) as raised:
            require_exact_event_ids(result)

        self.assertFalse(raised.exception.request_sent)
        self.assertIn("No deletion request was sent", str(raised.exception))

    def test_deletion_planning_rejects_mixed_nested_event_shape(self):
        client = StaticEventClient(
            {
                "results": [
                    {"eventId": 101},
                    {"search": {"form": "Synthetic Wellness"}, "results": [{"eventId": 102}]},
                ]
            }
        )
        records = [
            {
                "form": "Synthetic Wellness",
                "user_id": 1,
                "start_date": "01/05/2026",
                "Score": 5,
            }
        ]

        with self.assertRaisesRegex(ValueError, "direct records and nested result batches were mixed"):
            plan_event_deletions(client, records)

    def test_load_example_event_workflow_input_uses_example_training_load_data(self):
        target = load_example_event_workflow_input()

        self.assertEqual(target.form, "Training Load")
        self.assertEqual(target.user_id, 60521)
        self.assertEqual(target.about, "NOC01 MaleAthlete")
        self.assertEqual(target.date_range, ("14/04/2026", "08/06/2026"))
        self.assertEqual(target.expected_upload_count, 69)
        self.assertEqual(target.records[0]["start_time"], "09:00")
        self.assertEqual(target.records[0]["Form ID"], "5000001")

    def test_run_event_replay_workflow_counts_delete_and_reinsert_for_example_target(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_event_replay_workflow(
                client,
                target,
                base_dir=tmp,
                dry_run=False,
                confirm=True,
            )
            operation_dir = Path(summary["operation_dir"])
            manifest_path = Path(summary["manifest_path"])

            self.assertEqual(summary["counts"]["before"]["entry_count"], target.expected_upload_count)
            self.assertEqual(summary["counts"]["after_delete"]["entry_count"], 0)
            self.assertEqual(summary["counts"]["after_upload"]["entry_count"], target.expected_upload_count)
            self.assertEqual(summary["preflight"]["delete_count"], target.expected_upload_count)
            self.assertEqual(summary["preflight"]["warnings"], [])
            self.assertTrue(operation_dir.exists())
            self.assertTrue((operation_dir / "payloads/02_delete_event_payload.json").exists())
            self.assertTrue((operation_dir / "payloads/04_insert_event_payload.json").exists())
            self.assertTrue((operation_dir / "workflow_summary.json").exists())
            self.assertTrue((operation_dir / "raw_json/02_preflight_diff.json").exists())
            self.assertIn("count_before", manifest_path.read_text(encoding="utf-8"))
            self.assertIn("count_after_upload", manifest_path.read_text(encoding="utf-8"))

    def test_run_event_replay_workflow_warns_when_more_existing_events_are_deleted_than_uploaded(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        duplicate = dict(client.events[0])
        duplicate["eventId"] = client.next_event_id
        client.next_event_id += 1
        client.events.append(duplicate)

        with tempfile.TemporaryDirectory() as tmp:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                summary = run_event_replay_workflow(
                    client,
                    target,
                    base_dir=tmp,
                    dry_run=True,
                    confirm=False,
                )

        self.assertEqual(summary["preflight"]["delete_count"], target.expected_upload_count + 1)
        self.assertEqual(len(summary["preflight"]["warnings"]), 1)
        self.assertIn("scheduled for deletion but only", summary["preflight"]["warnings"][0])
        self.assertEqual(len(caught), 1)
        self.assertIn("same number of datapoints is uploaded", str(caught[0].message))

    def test_run_event_replay_workflow_preserves_unmatched_events_in_same_date_range(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        unrelated = dict(client.events[0])
        unrelated["eventId"] = client.next_event_id
        client.next_event_id += 1
        unrelated["rows"] = [{"row": 0, "pairs": [{"key": "Form ID", "value": "UNRELATED-1"}]}]
        client.events.append(unrelated)

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_event_replay_workflow(
                client,
                target,
                base_dir=tmp,
                dry_run=False,
                confirm=True,
            )

        self.assertEqual(summary["preflight"]["delete_count"], target.expected_upload_count)
        self.assertEqual(summary["preflight"]["unmatched_existing_count"], 1)
        self.assertEqual(summary["counts"]["after_delete"]["entry_count"], 1)
        self.assertEqual(summary["counts"]["after_upload"]["entry_count"], target.expected_upload_count + 1)

    def test_run_event_replay_workflow_can_delete_all_events_in_range_in_sandbox(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        unrelated = dict(client.events[0])
        unrelated["eventId"] = client.next_event_id
        client.next_event_id += 1
        unrelated["rows"] = [{"row": 0, "pairs": [{"key": "Form ID", "value": "UNRELATED-1"}]}]
        client.events.append(unrelated)

        with tempfile.TemporaryDirectory() as tmp:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                summary = run_event_replay_workflow(
                    client,
                    target,
                    base_dir=tmp,
                    dry_run=False,
                    confirm=True,
                    delete_all_in_range=True,
                )

        self.assertEqual(summary["preflight"]["match_strategy"], "full_range")
        self.assertEqual(summary["preflight"]["delete_count"], target.expected_upload_count + 1)
        self.assertEqual(len(caught), 1)
        self.assertEqual(summary["counts"]["after_delete"]["entry_count"], 0)
        self.assertEqual(summary["counts"]["after_upload"]["entry_count"], target.expected_upload_count)

    def test_run_event_replay_workflow_rejects_delete_all_in_range_outside_sandbox(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target, sandbox=False)

        with self.assertRaisesRegex(PermissionError, "delete_all_in_range"):
            run_event_replay_workflow(
                client,
                target,
                dry_run=True,
                confirm=False,
                delete_all_in_range=True,
            )

    def test_plan_event_deletions_summarizes_targeted_deletes(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        unrelated = dict(client.events[0])
        unrelated["eventId"] = client.next_event_id
        client.next_event_id += 1
        unrelated["rows"] = [{"row": 0, "pairs": [{"key": "Form ID", "value": "UNRELATED-1"}]}]
        client.events.append(unrelated)

        plans = plan_event_deletions(client, target.records, form=target.form)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["form"], target.form)
        self.assertEqual(plans[0]["user_id"], target.user_id)
        self.assertEqual(plans[0]["delete_count"], target.expected_upload_count)
        self.assertEqual(plans[0]["unmatched_existing_count"], 1)

    def test_plan_event_deletions_supports_full_range_mode(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        duplicate = dict(client.events[0])
        duplicate["eventId"] = client.next_event_id
        client.next_event_id += 1
        client.events.append(duplicate)

        plans = plan_event_deletions(client, target.records, form=target.form, delete_all_for_targets=True)

        self.assertEqual(plans[0]["match_strategy"], "full_range")
        self.assertEqual(plans[0]["delete_count"], target.expected_upload_count + 1)
        self.assertTrue(plans[0]["delete_all_for_targets"])

    def test_run_event_replace_workflow_replaces_records_for_generic_inputs(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        unrelated = dict(client.events[0])
        unrelated["eventId"] = client.next_event_id
        client.next_event_id += 1
        unrelated["rows"] = [{"row": 0, "pairs": [{"key": "Form ID", "value": "UNRELATED-1"}]}]
        client.events.append(unrelated)

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_event_replace_workflow(
                client,
                target.records,
                form=target.form,
                base_dir=tmp,
                dry_run=False,
                confirm=True,
            )
            operation_dir = Path(summary["operation_dir"])
            self.assertTrue((operation_dir / "raw_json/01_deletion_plan.json").exists())
            self.assertTrue((operation_dir / "payloads/04_insert_event_payload.json").exists())

        self.assertEqual(summary["target_count"], 1)
        self.assertEqual(summary["targets"][0]["delete_count"], target.expected_upload_count)
        self.assertEqual(summary["counts"]["after_delete"][0]["entry_count"], 1)
        self.assertEqual(summary["counts"]["after_upload"][0]["entry_count"], target.expected_upload_count + 1)

    def test_run_event_delete_workflow_deletes_without_uploading(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_event_delete_workflow(
                client,
                target,
                base_dir=tmp,
                dry_run=False,
                confirm=True,
            )
            operation_dir = Path(summary["operation_dir"])
            self.assertTrue((operation_dir / "payloads/02_delete_event_payload.json").exists())
            self.assertTrue((operation_dir / "raw_json/03_count_after_delete.json").exists())

        self.assertEqual(summary["counts"]["before"]["entry_count"], target.expected_upload_count)
        self.assertEqual(summary["counts"]["after_delete"]["entry_count"], 0)
        self.assertEqual(summary["preflight"]["delete_count"], target.expected_upload_count)
        self.assertEqual(client.insert_calls, 0)

    def test_run_event_delete_workflow_can_delete_all_events_in_range_in_sandbox(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target)
        unrelated = dict(client.events[0])
        unrelated["eventId"] = client.next_event_id
        client.next_event_id += 1
        unrelated["rows"] = [{"row": 0, "pairs": [{"key": "Form ID", "value": "UNRELATED-1"}]}]
        client.events.append(unrelated)

        with tempfile.TemporaryDirectory() as tmp:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                summary = run_event_delete_workflow(
                    client,
                    target,
                    base_dir=tmp,
                    dry_run=False,
                    confirm=True,
                    delete_all_in_range=True,
                )

        self.assertEqual(summary["preflight"]["match_strategy"], "full_range")
        self.assertEqual(summary["preflight"]["delete_count"], target.expected_upload_count + 1)
        self.assertEqual(summary["counts"]["after_delete"]["entry_count"], 0)
        self.assertEqual(client.insert_calls, 0)
        self.assertEqual(len(caught), 1)

    def test_run_event_delete_workflow_rejects_delete_all_in_range_outside_sandbox(self):
        target = load_example_event_workflow_input()
        client = ReplayClient(target, sandbox=False)

        with self.assertRaisesRegex(PermissionError, "delete_all_in_range"):
            run_event_delete_workflow(
                client,
                target,
                dry_run=True,
                confirm=False,
                delete_all_in_range=True,
            )


if __name__ == "__main__":
    unittest.main()
