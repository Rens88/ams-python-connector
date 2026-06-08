library(smartabaseR)

# Minimal Smartabase smoke test.
# Preferred credential object:
# info <- list(username = "your.username", password = "your.password")
#
# If `info` does not already exist, this script tries to read `.env` and build
# the same named list from SMARTABASE_USERNAME and SMARTABASE_PASSWORD.

if (file.exists(".env")) {
  readRenviron(".env")
}

url <- Sys.getenv("SMARTABASE_URL", unset = "teamnl.smartabase.nl/sandbox")
profile_form <- Sys.getenv("SMARTABASE_PROFILE_FORM", unset = "")
if (!nzchar(profile_form)) {
  profile_form <- Sys.getenv("SMARTABASE_DEFAULT_FORM", unset = "Personal Zones")
}

user_key <- Sys.getenv("SMARTABASE_USER_KEY", unset = "")
user_value <- Sys.getenv(
  "SMARTABASE_USER_VALUE",
  unset = Sys.getenv("SMARTABASE_ATHLETE_GROUP", unset = "")
)
include_all_cols <- tolower(Sys.getenv("SMARTABASE_INCLUDE_ALL_COLS", unset = "true")) %in%
  c("1", "true", "yes")

if (!exists("info")) {
  info <- list(
    username = Sys.getenv("SMARTABASE_USERNAME", unset = ""),
    password = Sys.getenv("SMARTABASE_PASSWORD", unset = "")
  )
}

if (!is.list(info) ||
    is.null(info$username) || !nzchar(info$username) ||
    is.null(info$password) || !nzchar(info$password)) {
  stop(
    paste(
      "Missing Smartabase login info.",
      "Create `info <- list(username = ..., password = ...)` before sourcing this file,",
      "or set SMARTABASE_USERNAME and SMARTABASE_PASSWORD in `.env`."
    ),
    call. = FALSE
  )
}

message("Using Smartabase URL: ", url)
message("Using Smartabase user: ", info$username)
message("Using profile form: ", profile_form)

user_filter <- smartabaseR::sb_get_user_filter()
profile_filter <- smartabaseR::sb_get_profile_filter()

if (nzchar(user_key)) {
  if (user_key == "current_group") {
    user_filter <- smartabaseR::sb_get_user_filter(user_key = user_key)
    profile_filter <- smartabaseR::sb_get_profile_filter(user_key = user_key)
  } else {
    user_filter <- smartabaseR::sb_get_user_filter(
      user_key = user_key,
      user_value = user_value
    )
    profile_filter <- smartabaseR::sb_get_profile_filter(
      user_key = user_key,
      user_value = user_value
    )
  }
}

users <- smartabaseR::sb_get_user(
  url = url,
  username = info$username,
  password = info$password,
  filter = user_filter,
  option = smartabaseR::sb_get_user_option(
    include_all_cols = include_all_cols,
    guess_col_type = FALSE,
    interactive_mode = FALSE
  )
)

message("\nUsers:")
print(utils::head(users, 10))
message("User columns: ", paste(names(users), collapse = ", "))

profile_rows <- smartabaseR::sb_get_profile(
  form = profile_form,
  url = url,
  username = info$username,
  password = info$password,
  filter = profile_filter,
  option = smartabaseR::sb_get_profile_option(
    guess_col_type = FALSE,
    interactive_mode = FALSE
  )
)

message("\nProfile rows:")
print(utils::head(profile_rows, 10))
message("Profile columns: ", paste(names(profile_rows), collapse = ", "))
