"""Bounded public-document acquisition followed by isolated Chromium rendering.

Chromium never receives network access through page requests: only the fetched
main document is fulfilled, all other requests are aborted. DNS is resolved and
validated once per redirect, then the socket is pinned to that validated address.
"""
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
from urllib.parse import urlsplit, urljoin, urldefrag

MAX_BYTES = 1_048_576
MAX_TEXT = 20_000
REPO = Path(__file__).resolve().parents[2]

def read_chrome_results(cancel, expected_url=None):
    from adapters import run_process
    script = '''tell application "Google Chrome"
if (count of windows) is 0 then error "Open a Google search in Chrome first"
set currentURL to URL of active tab of front window
if currentURL does not start with "https://www.google.com/search?" then error "Open a Google search results tab first"
set pageText to execute active tab of front window javascript "document.body.innerText.slice(0,12000)"
return currentURL & linefeed & pageText
end tell'''
    try:
        output = run_process(['/usr/bin/osascript', '-'], cancel, timeout=20, input_text=script)
    except RuntimeError as error:
        if 'JavaScript through AppleScript is turned off' in str(error):
            raise ValueError('In Chrome enable View → Developer → Allow JavaScript from Apple Events, then try again.') from error
        raise
    url, separator, content = output.partition('\n')
    if expected_url and url != expected_url:
        raise ValueError('The active Chrome tab changed before results could be read; retry the research request.')
    if not separator or not content.strip():
        raise ValueError('Chrome returned no readable results. Wait for the page to load and try again.')
    validate_url(url)
    return {'url': url, 'text': content[:12000]}

def research_query(command):
    from mac_items import without_address
    text = without_address(command)
    text = re.sub(r'^(?:(?:please|can you|could you|would you)\s+)+', '', text, flags=re.I)
    if re.search(r"\b(?:don't|do not|never|send|post|upload|delete)\b", text, re.I):
        return None
    match = re.fullmatch(r'(?:research|investigate)\s+(?:about\s+)?(.+?)\s*[.!?]*', text.strip(), re.I)
    return match[1].strip() if match else None

def research_chrome(command, cancel, helper):
    import time
    query = research_query(command)
    if not query:
        raise ValueError('Give a topic to research.')
    opened, evidence = search_chrome('search Chrome for ' + query, cancel, helper)
    # Wait briefly for Chrome to populate its tab; cancellation remains responsive.
    if cancel.wait(2):
        from adapters import Cancelled
        raise Cancelled('Research cancelled; the opened search tab remains visible.')
    page = read_chrome_results(cancel, expected_url=opened['url'])
    if len(page['text'].strip()) < 100:
        raise ValueError('The search results have not loaded yet. Please try again.')
    return page, evidence

def research_articles(page, root, cancel):
    """Read up to three public result articles through the isolated reader."""
    from adapters import Cancelled, run_process
    script = '''on run argv
tell application "Google Chrome"
if URL of active tab of front window is not (item 1 of argv) then error "Search tab changed"
return execute active tab of front window javascript "JSON.stringify(Array.from(document.querySelectorAll('a:has(h3)')).map(a => a.href).slice(0,12))"
end tell
end run'''
    raw = run_process(['/usr/bin/osascript', '-', page['url']], cancel, timeout=20, input_text=script)
    urls = json.loads(raw)
    if not isinstance(urls, list):
        raise ValueError('Could not read search result links')
    articles, seen, attempted = [], set(), 0
    for candidate in urls[:12]:
        if cancel.is_set():
            raise Cancelled('Research cancelled; the search tab remains open.')
        try:
            url = validate_url(candidate)
            host = urlsplit(url).hostname.lower()
            if host == 'google.com' or host.endswith('.google.com') or host in seen:
                continue
            seen.add(host)
            attempted += 1
            article = execute_browser('browser.read', 'read page: ' + url, root, cancel)
            if len(article['text'].strip()) >= 200:
                articles.append(article)
            if len(articles) >= 3:
                break
        except Cancelled:
            raise
        except (ValueError, RuntimeError, TimeoutError, OSError):
            pass
        if attempted >= 5:
            break
    if not articles:
        raise ValueError('Search opened, but no result articles could be read. Try another topic.')
    return articles

def chrome_query(command):
    from mac_items import without_address
    text = without_address(command)
    text = re.sub(r'^(?:(?:please|can you|could you|would you)\s+)+', '', text, flags=re.I).strip()
    if re.search(r"\b(?:don't|do not|never|send|post|upload|delete)\b", text, re.I):
        return None
    if re.fullmatch(r'open\s+(?:the\s+)?google(?:\s+(?:home\s*page|website))?[.!?]*', text, re.I):
        return ''
    text = re.sub(r'^open\s+(?:google\s+)?chrome\s+(?:and|then)\s+', '', text, flags=re.I)
    # Browser location can precede or follow the topic. Preserve the topic itself.
    text = re.sub(r'\s+(?:on|in|using|with)\s+(?:google\s+chrome|chrome|google|the web|the internet)[.!?]*$', '', text, flags=re.I)
    match = re.fullmatch(r'(?:search(?:\s+(?:the web|the internet|online|google chrome|chrome|google))?|look\s+up|google)\s+(?:for\s+)?(.+?)\s*[.!?]*', text, re.I)
    if not match:
        return None
    query = match[1].strip()
    if re.search(r'\b(?:files?|folders?|directory|finder|memory)\b|(?:^|\s)(?:/|~/)', query, re.I):
        return None
    return query

def search_chrome(command, cancel, helper):
    from urllib.parse import urlencode
    from adapters import run_process
    query = chrome_query(command)
    if query is None:
        raise ValueError('Search terms required')
    url = 'https://www.google.com/search?' + urlencode({'q': query})
    script = '''on run argv
set targetURL to item 1 of argv
tell application "Google Chrome"
activate
if (count of windows) is 0 then make new window
set searchTab to make new tab at end of tabs of front window with properties {URL:targetURL}
set active tab index of front window to count of tabs of front window
repeat 40 times
if URL of searchTab is targetURL then return URL of searchTab
delay 0.1
end repeat
error "Chrome tab URL verification failed"
end tell
end run'''
    observed = run_process(['/usr/bin/osascript', '-', url], cancel, timeout=20, input_text=script)
    if observed != url:
        raise ValueError('Chrome tab URL verification failed')
    return {'message': 'Opened a Chrome search for ' + query + '.' if query else 'Opened Google in Chrome.', 'url': url}, [{'check': 'Chrome tab URL read-back', 'application': 'com.google.Chrome', 'url': observed}]


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in url) or '\\' in url:
        raise ValueError('Invalid public URL')
    parts = urlsplit(url)
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError('Only public HTTP(S) URLs without credentials are allowed')
    if parts.port not in (None, 80 if parts.scheme == 'http' else 443):
        raise ValueError('Only standard HTTP(S) ports are allowed')
    host = parts.hostname.lower().rstrip('.')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Private host rejected')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (not address.is_global or address.is_multicast):
        raise ValueError('Non-public address rejected')
    return urldefrag(url)[0]


def public_addresses(url):
    parts = urlsplit(validate_url(url))
    records = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast for address in addresses):
        raise ValueError('DNS returned a non-public address')
    return addresses


def fetch_once(url):
    parts = urlsplit(validate_url(url))
    address = public_addresses(url)[0]
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    connection = http.client.HTTPConnection(parts.hostname, port, timeout=8)
    # Connect to the already checked numeric address. Never re-resolve the host.
    connection.sock = socket.create_connection((address, port), timeout=8)
    try:
        if parts.scheme == 'https':
            import certifi
            connection.sock = ssl.create_default_context(cafile=certifi.where()).wrap_socket(connection.sock, server_hostname=parts.hostname)
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        connection.request('GET', path, headers={'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity', 'User-Agent': 'JARVIS-PublicReader/1.0'})
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        body = response.read(MAX_BYTES + 1)
        return response.status, headers, body
    finally:
        connection.close()


def fetch_document(url):
    current = validate_url(url)
    for _ in range(6):
        status, headers, body = fetch_once(current)
        if status in (301, 302, 303, 307, 308):
            if not headers.get('location'):
                raise ValueError('Redirect missing location')
            current = validate_url(urljoin(current, headers['location']))
            continue
        if status != 200:
            raise ValueError('Public page returned HTTP ' + str(status))
        if len(body) > MAX_BYTES:
            raise ValueError('Page exceeds byte limit')
        content_type = headers.get('content-type', '').split(';')[0].strip().lower()
        if content_type not in ('text/html', 'text/plain') or 'attachment' in headers.get('content-disposition', '').lower():
            raise ValueError('Downloads and non-text documents are blocked')
        if headers.get('content-encoding', 'identity').lower() != 'identity':
            raise ValueError('Encoded response rejected')
        return current, headers.get('content-type'), body
    raise ValueError('Too many redirects')


def render_document(url, content_type, body, project=REPO):
    from playwright.sync_api import sync_playwright
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(project) / '.runtime/browser-binaries')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--disable-background-networking'])
        try:
            context = browser.new_context(java_script_enabled=False, accept_downloads=False, service_workers='block')
            supplied = False
            def route_request(route):
                nonlocal supplied
                request = route.request
                if not supplied and request.is_navigation_request() and request.resource_type == 'document' and request.frame == page.main_frame and request.method == 'GET':
                    supplied = True
                    route.fulfill(status=200, body=body, headers={'content-type': content_type,
                        'content-security-policy': "default-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'; sandbox"})
                else:
                    route.abort('blockedbyclient')
            context.route('**/*', route_request)
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=10000)
            title = page.title()[:500]
            text = page.locator('body').inner_text(timeout=5000)
            context.close()
        finally:
            browser.close()
    return {'source_url': url, 'title': title, 'text': text[:MAX_TEXT],
            'sha256': hashlib.sha256(text[:MAX_TEXT].encode()).hexdigest(),
            'truncated': len(text) > MAX_TEXT, 'scope': 'public-read', 'status': 200}


def execute_browser(capability, command, root, cancel):
    from adapters import Cancelled, run_process
    if capability != 'browser.read':
        raise ValueError('Unsupported browser capability')
    match = re.fullmatch(r'read page:\s*(https?://\S+)', command.strip(), re.IGNORECASE)
    if not match:
        raise ValueError('Expected read page: https://public-url')
    url = validate_url(match.group(1))
    if cancel.is_set():
        raise Cancelled('Cancelled before browser execution')
    project = Path(root).parent.parent
    runtime = project / '.runtime/browser/bin/python'
    if not runtime.is_file():
        raise RuntimeError('Browser runtime missing; run scripts/setup-browser.sh')
    output = run_process([str(runtime), str(Path(__file__).resolve()), '--read', url, '--project', str(project)], cancel, timeout=35)
    result = json.loads(output)
    verify_browser(capability, result, root)
    return result


def verify_browser(capability, result, root):
    if capability != 'browser.read' or result.get('scope') != 'public-read' or result.get('status') != 200:
        raise ValueError('Invalid browser result scope')
    validate_url(result['source_url'])
    text = result['text']
    if not isinstance(text, str) or len(text) > MAX_TEXT or not isinstance(result['title'], str) or len(result['title']) > 500:
        raise ValueError('Invalid browser output bounds')
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != result['sha256']:
        raise ValueError('Browser text integrity mismatch')
    return [{'check': 'captured browser text integrity (not factual verification)',
             'source_url': result['source_url'], 'sha256': digest, 'characters': len(text), 'scope': 'public-read'}]


if __name__ == '__main__':
    try:
        if len(sys.argv) not in (3, 5) or sys.argv[1] != '--read' or (len(sys.argv) == 5 and sys.argv[3] != '--project'):
            raise ValueError('Expected --read URL')
        project = Path(sys.argv[4]) if len(sys.argv) == 5 else REPO
        print(json.dumps(render_document(*fetch_document(sys.argv[2]), project=project)))
    except Exception as error:
        print(str(error)[:1000], file=sys.stderr)
        sys.exit(1)
