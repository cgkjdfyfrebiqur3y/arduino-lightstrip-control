import socket
import threading


class LightstripHandler:
    def __init__(self):
        self.strips = {
            0: 0,
            1: 0,
        }

        self.lock = threading.Lock()

    def handle(self, data, selected_strip):
        """
        Handle one complete protocol line.

        Returns:
            (response, selected_strip)

        response:
            String to send back to the client,
            or None for no response.
        """

        data = data.strip()
        parts = data.split()

        # strip 0 / strip 1
        if (
            len(parts) == 2
            and parts[0] == "strip"
            and parts[1] in ("0", "1")
        ):
            selected_strip = int(parts[1])

            print(f"Selected strip {selected_strip}")

            return None, selected_strip

        # state 0 / state 1
        if (
            len(parts) == 2
            and parts[0] == "state"
            and parts[1] in ("0", "1")
        ):
            if selected_strip is None:
                return "error", selected_strip

            state = int(parts[1])

            with self.lock:
                self.strips[selected_strip] = state

            print(
                f"Strip {selected_strip}: "
                f"state = {state}"
            )

            return None, selected_strip

        # status strip 0 / status strip 1
        if (
            len(parts) == 3
            and parts[0] == "status"
            and parts[1] == "strip"
            and parts[2] in ("0", "1")
        ):
            strip = int(parts[2])

            with self.lock:
                state = self.strips[strip]

            return str(state), selected_strip

        # status strip all
        if (
            len(parts) == 3
            and parts[0] == "status"
            and parts[1] == "strip"
            and parts[2] == "all"
        ):
            with self.lock:
                response = (
                    f"{self.strips[0]} "
                    f"{self.strips[1]}"
                )

            return response, selected_strip

        # endconn
        if data == "endconn":
            return None, selected_strip

        return "error", selected_strip


class LightstripServer:
    def __init__(self, handler=None):
        self.handler = handler or LightstripHandler()

    def serve(self, port, host="0.0.0.0"):
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        ) as server:

            server.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            server.bind((host, port))
            server.listen()

            print(
                f"Listening on "
                f"{host}:{port}"
            )

            while True:
                conn, addr = server.accept()

                threading.Thread(
                    target=self._client,
                    args=(conn, addr),
                    daemon=True
                ).start()

    def _client(self, conn, addr):
        buffer = b""
        selected_strip = None

        print(f"Connected: {addr}")

        try:
            while True:
                data = conn.recv(4096)

                if not data:
                    break

                buffer += data

                # TCP is a stream.
                # Only process complete lines.
                while b"\n" in buffer:
                    raw, buffer = buffer.split(
                        b"\n",
                        1
                    )

                    line = raw.decode(
                        "utf-8",
                        errors="replace"
                    ).strip()

                    if not line:
                        continue

                    response, selected_strip = (
                        self.handler.handle(
                            line,
                            selected_strip
                        )
                    )

                    if response is not None:
                        conn.sendall(
                            (
                                response + "\n"
                            ).encode("utf-8")
                        )

                    if line == "endconn":
                        return

        except (
            ConnectionResetError,
            BrokenPipeError
        ):
            pass

        finally:
            conn.close()

            print(
                f"Disconnected: {addr}"
            )


if __name__ == "__main__":
    LightstripServer().serve(
        port=1025,
        host="0.0.0.0"
    )