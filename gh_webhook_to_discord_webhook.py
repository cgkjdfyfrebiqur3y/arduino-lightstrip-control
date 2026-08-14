#!/usr/bin/env python3

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "0.0.0.0"
PORT = 8080

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1537837094599397466/BDuNydXnFTOEj3h0buEu4o0zmtAvcciH8OnnRJG4TTElcNInnCNSfhI7Mtk13CyGhbyF"


def send_discord(message):
    data = json.dumps({
        "content": message
    }).encode("utf-8")

    request = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Webhook-Server"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def describe_event(event, data):
    # ---------------------------------------------------------
    # PUSH
    # ---------------------------------------------------------

    if event == "push":
        repository = data["repository"]["full_name"]
        sender = data["sender"]["login"]
        branch = data["ref"].removeprefix("refs/heads/")

        commits = data.get("commits", [])

        lines = [
            f"{sender} pushed {len(commits)} commit(s) to {repository}.",
            f"Branch: {branch}",
            ""
        ]

        for commit in commits:
            message = commit["message"].split("\n", 1)[0]
            sha = commit["id"][:7]

            lines.append(f"{sha} {message}")

        return "\n".join(lines)

    # ---------------------------------------------------------
    # PULL REQUEST
    # ---------------------------------------------------------

    if event == "pull_request":
        action = data["action"]
        pr = data["pull_request"]

        number = data["number"]
        title = pr["title"]
        user = pr["user"]["login"]

        description = pr.get("body") or "(no description)"

        head = pr["head"]["ref"]
        base = pr["base"]["ref"]

        return (
            f"Pull request #{number} was {action} by {user}.\n\n"
            f"Title: {title}\n"
            f"Description:\n{description}\n\n"
            f"Branch: {head} -> {base}"
        )

    # ---------------------------------------------------------
    # ISSUES
    # ---------------------------------------------------------

    if event == "issues":
        action = data["action"]
        issue = data["issue"]

        number = issue["number"]
        title = issue["title"]
        user = issue["user"]["login"]

        description = issue.get("body") or "(no description)"

        return (
            f"Issue #{number} was {action} by {user}.\n\n"
            f"Title: {title}\n"
            f"Description:\n{description}"
        )

    # ---------------------------------------------------------
    # RELEASE
    # ---------------------------------------------------------

    if event == "release":
        action = data["action"]
        release = data["release"]

        tag = release["tag_name"]
        name = release.get("name") or tag
        user = release["author"]["login"]

        description = release.get("body") or "(no description)"

        return (
            f"Release {tag} was {action} by {user}.\n\n"
            f"Name: {name}\n"
            f"Description:\n{description}"
        )

    # ---------------------------------------------------------
    # UNKNOWN EVENT
    # ---------------------------------------------------------

    return (
        f"GitHub event: {event}\n"
        f"Repository: {data.get('repository', {}).get('full_name', 'unknown')}\n"
        f"Action: {data.get('action', 'unknown')}"
    )


class GitHubWebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)

            data = json.loads(raw.decode("utf-8"))

            event = self.headers.get("X-GitHub-Event", "unknown")

            message = describe_event(event, data)

            print()
            print(message)
            print()

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

        except Exception as e:
            print(f"Webhook error: {e}")

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
        response = b"GitHub webhook server\n"

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
        pass


def main():
    server = ThreadingHTTPServer(
        (HOST, PORT),
        GitHubWebhookHandler
    )

    print(f"Listening on {HOST}:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()