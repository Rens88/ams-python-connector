library(smartabaseR)

# Minimal Smartabase smoke test.
# Preferred credential object:
# info <- list(username = "your.username", password = "your.password")
#
# This script prefers the repository-root `.env` file when present, and only
# falls back to an existing `info` object if the environment variables are not
# populated.

find_script_path <- function() {
  frames <- sys.frames()
  for (index in rev(seq_along(frames))) {
    candidate <- frames[[index]]$ofile
    if (!is.null(candidate)) {
      return(normalizePath(candidate, winslash = "/", mustWork = TRUE))
    }
  }
  normalizePath("legacy_code/connect_ams.R", winslash = "/", mustWork = FALSE)
}

script_path <- find_script_path()
repo_root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
env_path <- file.path(repo_root, ".env")

if (file.exists(env_path)) {
  message("Reading .env file for Smartabase credentials: ", env_path)
  readRenviron(env_path)
} else {
  message(
    "No repo-root .env file found at ", env_path,
    ". You can create one there, or define `info <- list(username = ..., password = ...)` before sourcing this file."
  )
}

url <- Sys.getenv("SMARTABASE_URL", unset = "make-sure-smartabas_url-is-set")
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

env_info <- list(
  username = Sys.getenv("SMARTABASE_USERNAME", unset = ""),
  password = Sys.getenv("SMARTABASE_PASSWORD", unset = "")
)

if (nzchar(env_info$username) && nzchar(env_info$password)) {
  info <- env_info
  message("Using credentials from repo-root .env / environment variables.")
} else if (!exists("info")) {
  info <- list(
    username = "",
    password = ""
  )
} else {
  message("Using pre-existing `info` object from the current R session.")
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

message("Using user filter: ", user_filter)
message("Using profile filter: ", profile_filter)
message("Using include_all_cols: ", include_all_cols)


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
