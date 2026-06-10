library(smartabaseR)

find_script_path <- function() {
  frames <- sys.frames()
  for (index in rev(seq_along(frames))) {
    candidate <- frames[[index]]$ofile
    if (!is.null(candidate)) {
      return(normalizePath(candidate, winslash = "/", mustWork = TRUE))
    }
  }
  normalizePath("legacy_code/smoke_test_groups.R", winslash = "/", mustWork = FALSE)
}

script_path <- find_script_path()
repo_root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
env_path <- file.path(repo_root, ".env")

if (file.exists(env_path)) {
  readRenviron(env_path)
} else {
  stop("Missing repo-root .env file: ", env_path, call. = FALSE)
}

url <- Sys.getenv("SMARTABASE_URL", unset = "")
username <- Sys.getenv("SMARTABASE_USERNAME", unset = "")
password <- Sys.getenv("SMARTABASE_PASSWORD", unset = "")
group_name <- Sys.getenv("SMARTABASE_ATHLETE_GROUP", unset = "")

if (!nzchar(url) || !nzchar(username) || !nzchar(password)) {
  stop("SMARTABASE_URL, SMARTABASE_USERNAME and SMARTABASE_PASSWORD must be set in .env.", call. = FALSE)
}

groups <- smartabaseR::sb_get_group(
  url = url,
  username = username,
  password = password
)

message("Legacy group smoke test succeeded.")
print(utils::head(groups, 10))

if (nzchar(group_name)) {
  group_users <- smartabaseR::sb_get_user(
    url = url,
    username = username,
    password = password,
    filter = smartabaseR::sb_get_user_filter(
      user_key = "group",
      user_value = group_name
    ),
    option = smartabaseR::sb_get_user_option(
      guess_col_type = FALSE,
      interactive_mode = FALSE
    )
  )

  message("Legacy group user smoke test succeeded for group: ", group_name)
  print(utils::head(group_users, 10))
}
