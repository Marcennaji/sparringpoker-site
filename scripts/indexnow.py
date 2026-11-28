"""Submit SparringPoker URL changes to IndexNow after a deployment."""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
HOST = "sparringpoker.com"
ORIGIN = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"
CONTENT_TYPE = "application/json; charset=utf-8"
TIMEOUT = 15
SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
NON_SITE_DIRS = {"app-doc", "doc", "docs", "documentation", "scripts", "tests"}
ASSET_EXTENSIONS = {
    ".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".avif",
}
RESPONSE_MESSAGES = {
    200: "Submission successful. Indexing is not guaranteed.",
    202: "Submission accepted. Key validation is pending. Indexing is not guaranteed.",
    400: "Invalid request format.",
    403: "Key validation failed. Check the deployed key file.",
    422: "One or more URLs do not belong to the host, or the key is invalid.",
    429: "Too many requests. Wait before trying again.",
}


def site_url(url):
    """Validate a URL and normalize its scheme, host and empty path."""
    if re.search(r"[^A-Za-z0-9._~:/?@!$&'()*+,;=%-]|%(?![0-9A-Fa-f]{2})", url):
        raise ValueError(f"Invalid URL: {url!r}")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or parts.netloc.lower() != HOST:
        raise ValueError(f"Expected an absolute URL on {HOST}: {url!r}")
    return urlunsplit((parts.scheme, HOST, parts.path or "/", parts.query, ""))


def sitemap_urls(root):
    sitemap = ET.parse(root / "sitemap.xml")
    locations = sitemap.findall("sm:url/sm:loc", SITEMAP_NAMESPACE)
    if not locations:
        raise ValueError("No URL locations found in sitemap.xml.")
    return [site_url((location.text or "").strip()) for location in locations]


def find_key(root):
    matches = []
    for path in root.glob("*.txt"):
        key = path.stem
        if path.suffix != ".txt" or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
            continue
        if path.is_file() and path.read_bytes().strip() == key.encode("ascii"):
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(
            f"Expected one root IndexNow key file with matching name and contents, found {len(matches)}."
        )
    return matches[0]


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if result.returncode:
        details = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git {args[0]} failed: {details}")
    return result.stdout


def page_url(path):
    directory, _, filename = path.rpartition("/")
    if filename == "index.html":
        path = f"{directory}/" if directory else ""
    return f"{ORIGIN}/{quote(path)}"


def changed_urls(root, reference):
    revision = git(root, "rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
    base = revision.decode("ascii").strip()
    diff = git(
        root, "diff", "--no-ext-diff", "--name-status", "-z", "--find-renames",
        "--diff-filter=ADMRT", base, "HEAD", "--",
    )
    fields = iter(diff.decode("utf-8").split("\0")[:-1])
    urls, assets = set(), set()
    for status in fields:
        paths = [next(fields)]
        if status.startswith("R"):
            paths.append(next(fields))
        for path in paths:
            parts = path.split("/")
            top = parts[0].lower()
            if top in NON_SITE_DIRS or any(part.startswith((".", "_")) for part in parts):
                continue
            extension = PurePosixPath(path).suffix.lower()
            if top == "assets" and extension in {".html", ".md", ".rst", ".txt"}:
                continue
            if top == "assets" or extension in ASSET_EXTENSIONS:
                assets.add(path)
            elif extension == ".html":
                urls.add(page_url(path))
    return sorted(urls), sorted(assets)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def submit(body):
    request = Request(
        ENDPOINT, data=body.encode("utf-8"), method="POST", headers={"Content-Type": CONTENT_TYPE},
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=TIMEOUT) as response:
            return response.status
    except HTTPError as error:
        error.close()
        return error.code
    except OSError as error:
        raise ValueError(f"IndexNow request failed: {error}") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--all", action="store_true", help="use all canonical URLs in sitemap.xml")
    modes.add_argument("--since", metavar="REF", help="compare the deployed Git ref with HEAD")
    modes.add_argument("--url", action="extend", nargs="+", metavar="URL", help="use one or more explicit URLs")
    parser.add_argument("--dry-run", action="store_true", help="print the request without sending it")
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    try:
        if args.all:
            urls = sitemap_urls(ROOT)
        elif args.since is not None:
            urls, assets = changed_urls(ROOT, args.since)
            if assets:
                print("Shared assets changed and may affect additional pages.", file=sys.stderr)
                for asset in assets:
                    print(f"  {asset}", file=sys.stderr)
                print("Use --all if you want to submit every sitemap URL.", file=sys.stderr)
        else:
            urls = [site_url(url) for url in args.url]

        urls = list(dict.fromkeys(urls))
        if not urls:
            print("No relevant HTML changes. No request sent.")
            return 0
        if len(urls) > 10_000:
            raise ValueError("IndexNow allows up to 10,000 URLs per request.")

        key_file = find_key(ROOT)
        body = json.dumps({
            "host": HOST,
            "key": key_file.stem,
            "keyLocation": f"{ORIGIN}/{key_file.name}",
            "urlList": urls,
        }, indent=2)
        if args.dry_run:
            print(f"Dry run\nPOST {ENDPOINT}\nContent-Type: {CONTENT_TYPE}\n{body}")
            return 0
        status = submit(body)
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    success = status in {200, 202}
    message = RESPONSE_MESSAGES.get(status, "Unexpected response from IndexNow.")
    print(f"HTTP {status}: {message}", file=sys.stdout if success else sys.stderr)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
