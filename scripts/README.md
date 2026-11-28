# IndexNow for SparringPoker

Run these commands from the repository root with Python 3.8 or later. The script uses the Python standard library and calls Git for `--since`. On Windows, use `py -3` in place of `python` if that is how you launch Python.

**Wait for GitHub Pages to successfully deploy the intended commit before sending any notification.** For `--since`, make sure local `HEAD` is that deployed commit and use the previously deployed commit as the comparison reference.

| When | Command |
| --- | --- |
| Preview the initial submission | `python scripts/indexnow.py --all --dry-run` |
| Send the initial submission | `python scripts/indexnow.py --all` |
| Send a normal one-commit update, if the parent was deployed | `python scripts/indexnow.py --since HEAD~1` |
| Send an update spanning multiple commits | `python scripts/indexnow.py --since PREVIOUS_DEPLOYED_SHA` |
| Send selected URLs manually | `python scripts/indexnow.py --url https://sparringpoker.com/faq.html https://sparringpoker.com/support.html` |

Add `--dry-run` to any mode to print the POST endpoint and JSON without a network request. You can also repeat `--url`. Running the script without arguments shows help.

`--since` compares committed snapshots and includes the former URLs of deleted and renamed pages. Shared asset changes are listed so you can choose `--all` when they affect the whole site. Documentation, scripts, tests and hidden paths are ignored. If no page URLs qualify, the script exits successfully without sending a request.

| HTTP status | Meaning |
| --- | --- |
| 200 | Submission succeeded. |
| 202 | Submission accepted. IndexNow key validation is pending. |
| 400 | Invalid request format. |
| 403 | Key validation failed. Check that the deployed key file is reachable and contains the key. |
| 422 | A submitted URL falls outside the host, or the key format is invalid. |
| 429 | Too many requests. Wait before trying again. |

Neither 200 nor 202 guarantees indexing. The script sends one request to the official endpoint and exits with a nonzero status on failure. [IndexNow protocol documentation](https://www.indexnow.org/documentation)

Run the local tests with `python -B -m unittest discover -s scripts`.
