#!/usr/bin/env python3

import hashlib
import hmac
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "0.0.0.0"
PORT = 8080

GITHUB_SECRET = os.environ["gh_webhook_secret"]
DISCORD_WEBHOOK = os.environ["webhook_discord"]


def verify_github_signature(body, signature):
    if not signature:
        return False

    expected = "sha256=" + hmac.new(
        GITHUB_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def send_discord(message):
    data = json.dumps({
        "content": message
    }).encode("utf-8")

    request = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Webhook-Server",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def describe_event(event, data):
    repository = data.get("repository", {}).get(
        "full_name",
        "unknown repository"
    )

    # Push
    if event == "push":
        sender = data.get("sender", {}).get("login", "unknown")
        branch = data.get("ref", "").removeprefix("refs/heads/")
        commits = data.get("commits", [])

        lines = [
            f"{sender} pushed {len(commits)} commit(s) to {repository}.",
            f"Branch: {branch}",
        ]

        for commit in commits:
            sha = commit.get("id", "")[:7]
            message = commit.get("message", "").split("\n", 1)[0]

            lines.append(f"{sha} {message}")

        return "\n".join(lines)

    # Pull request
    if event == "pull_request":
        action = data.get("action", "changed")
        pr = data["pull_request"]

        number = data["number"]
        title = pr.get("title", "(no title)")
        user = pr.get("user", {}).get("login", "unknown")
        description = pr.get("body") or "(no description)"

        head = pr.get("head", {}).get("ref", "unknown")
        base = pr.get("base", {}).get("ref", "unknown")

        return (
            f"Pull request #{number} was {action} by {user}.\n\n"
            f"Title: {title}\n"
            f"Description:\n{description}\n\n"
            f"Branch: {head} -> {base}"
        )

    # Issue
    if event == "issues":
        action = data.get("action", "changed")
        issue = data["issue"]

        number = issue["number"]
        title = issue.get("title", "(no title)")
        user = issue.get("user", {}).get("login", "unknown")
        description = issue.get("body") or "(no description)"

        return (
            f"Issue #{number} was {action} by {user}.\n\n"
            f"Title: {title}\n"
            f"Description:\n{description}"
        )

    # Release
    if event == "release":
        action = data.get("action", "changed")
        release = data["release"]

        tag = release.get("tag_name", "unknown")
        name = release.get("name") or tag
        user = release.get("author", {}).get("login", "unknown")
        description = release.get("body") or "(no description)"

        return (
            f"Release {tag} was {action} by {user}.\n\n"
            f"Name: {name}\n"
            f"Description:\n{description}"
        )

    # Generic fallback for other GitHub events
    action = data.get("action")

    if action:
        return (
            f"GitHub event '{event}' happened in {repository}.\n"
            f"Action: {action}"
        )

    return f"GitHub event '{event}' happened in {repository}."


class GitHubWebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            body = self.rfile.read(content_length)

            # Verify GitHub's X-Hub-Signature-256.
            signature = self.headers.get(
                "X-Hub-Signature-256"
            )

            if not verify_github_signature(body, signature):
                self.send_response(401)
                self.send_header(
                    "Content-Type",
                    "text/plain; charset=utf-8"
                )
                self.end_headers()
                self.wfile.write(b"Invalid GitHub signature\n")
                return

            # Only parse the request after authentication.
            data = json.loads(body.decode("utf-8"))

            event = self.headers.get(
                "X-GitHub-Event",
                "unknown"
            )

            message = describe_event(event, data)

            print(message)

            send_discord(message)

            response = b"OK\n"

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(response))
            )
            self.end_headers()

            self.wfile.write(response)

        except json.JSONDecodeError:
            response = b"Invalid JSON\n"

            self.send_response(400)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(response))
            )
            self.end_headers()

            self.wfile.write(response)

        except Exception as error:
            print(f"Webhook error: {error}")

            response = b"Internal Server Error\n"

            self.send_response(500)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(response))
            )
            self.end_headers()

            self.wfile.write(response)

    def do_GET(self):
        response = b"GitHub webhook server is running\n"

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.send_header(
            "Content-Length",
            str(len(response))
        )
        self.end_headers()

        self.wfile.write(response)

    def log_message(self, format, *args):
        # Don't print the default HTTP access log.
        pass


def main():
    server = ThreadingHTTPServer(
        (HOST, PORT),
        GitHubWebhookHandler
    )

    print(f"GitHub webhook server listening on {HOST}:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()