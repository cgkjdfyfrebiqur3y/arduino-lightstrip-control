import socket
import threading


class LightstripHandler:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def handle(self, data):
        """
        Handle one complete protocol line.

        Returns:
            (response, target_session)
        """

        data = data.strip()

        # Initial session registration
        if data.isdigit():
            session = int(data)

            with self.lock:
                self.sessions[session] = None

            return str(session), session

        parts = data.split()

        # s_<session> strip 0/1
        if len(parts) == 3:
            session_name, command, value = parts

            if not session_name.startswith("s_"):
                return "error", None

            try:
                session = int(session_name[2:])
            except ValueError:
                return "error", None

            if command == "strip" and value in ("0", "1"):
                print(f"Session {session}: strip = {value}")

                return None, session

            if command == "state" and value in ("0", "1"):
                print(f"Session {session}: state = {value}")

                return None, session

        # s_<session> endconn
        if len(parts) == 2:
            session_name, command = parts

            if (
                session_name.startswith("s_")
                and command == "endconn"
            ):
                try:
                    session = int(session_name[2:])
                except ValueError:
                    return "error", None

                with self.lock:
                    self.sessions.pop(session, None)

                print(f"Session {session}: disconnect")

                return None, session

        return "error", None


class LightstripServer:
    def __init__(self, handler=None):
        self.handler = handler or LightstripHandler()

    def serve(self, port, host="0.0.0.0"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            server.bind((host, port))
            server.listen()

            print(f"Listening on {host}:{port}")

            while True:
                conn, addr = server.accept()

                threading.Thread(
                    target=self._client,
                    args=(conn, addr),
                    daemon=True
                ).start()

    def _client(self, conn, addr):
        session = None
        buffer = b""

        print(f"Connected: {addr}")

        try:
            while True:
                data = conn.recv(4096)

                if not data:
                    break

                buffer += data

                # TCP is a stream, so process complete lines only.
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)

                    line = raw.decode(
                        "utf-8",
                        errors="replace"
                    ).strip()

                    if not line:
                        continue

                    response, target_session = self.handler.handle(line)

                    # First message establishes the session.
                    if session is None and line.isdigit():
                        session = int(line)

                        with self.handler.lock:
                            self.handler.sessions[session] = conn

                    if response is not None:
                        conn.sendall(
                            (response + "\n").encode("utf-8")
                        )

                    # Explicit endconn
                    if line.endswith(" endconn"):
                        return

        except (ConnectionResetError, BrokenPipeError):
            pass

        finally:
            if session is not None:
                with self.handler.lock:
                    if self.handler.sessions.get(session) is conn:
                        del self.handler.sessions[session]

            conn.close()

            print(f"Disconnected: {addr}")