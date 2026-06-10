library(smartabaseR)

find_script_path <- function() {
  frames <- sys.frames()
  for (index in rev(seq_along(frames))) {
    candidate <- frames[[index]]$ofile
    if (!is.null(candidate)) {
      return(normalizePath(candidate, winslash = "/", mustWork = TRUE))
    }
  }
  normalizePath("legacy_code/smoke_test_login.R", winslash = "/", mustWork = FALSE)
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

if (!nzchar(url) || !nzchar(username) || !nzchar(password)) {
  stop("SMARTABASE_URL, SMARTABASE_USERNAME and SMARTABASE_PASSWORD must be set in .env.", call. = FALSE)
}

login <- smartabaseR::sb_login(
  url = url,
  username = username,
  password = password,
  option = smartabaseR::sb_login_option(interactive_mode = FALSE)
)

message("Legacy login smoke test succeeded.")
utils::str(login, max.level = 1)
