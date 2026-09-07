"""Length-prefixed pickle framing over a socket.

`ObjectStream` is the wire format the TCP backends use to move located values
between party processes. It exists because a TCP socket is a byte stream with no
message boundaries: this module adds the framing that lets a receiver know
where one Python object ends and the next begins.

!!! warning "Unpickling is not safe against untrusted peers"
    Objects are serialized with `pickle`, and unpickling data executes arbitrary
    code chosen by the sender. The stream performs no authentication and no
    encryption, so a PyChor deployment must run over a trusted network, or
    inside a tunnel that provides both.
"""

import pickle
import socket
from typing import Any

class ObjectStream:
    """A bidirectional stream of pickled Python objects over one socket.

    Each object is framed as a 4-byte big-endian unsigned length followed by
    that many bytes of pickle data. Writes are flushed immediately, so a
    `put_obj` on one side unblocks a `get_obj` on the other without further
    prompting.

    The stream is not internally synchronized: a single stream should be used by
    one thread at a time. The TCP backends satisfy this by giving each pair of
    parties its own stream and doing all sends from the choreography's single
    thread of control.

    Instances can be used as context managers, and close themselves when
    garbage collected.

    Args:
        sock: A connected stream socket. The stream takes ownership of it and
            closes it in `close`.

    Example:
        ```python
        with ObjectStream(sock) as stream:
            stream.put_obj({"share": 42})
            reply = stream.get_obj()
        ```
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.writer = sock.makefile('wb')
        self.reader = sock.makefile('rb')

    # Objects are sent/received as a 4-byte big-endian integer of
    # the pickled object data length, followed by the pickled data.

    def get_obj(self) -> Any:
        """Read the next object from the stream, blocking until it arrives.

        Returns:
            The unpickled object, or `None` if the peer closed the connection
            before sending another frame. Note that a legitimately sent `None`
            is indistinguishable from end-of-stream.
        """
        header = self.reader.read(4)
        if not header:
            return None
        length = int.from_bytes(header,'big')
        return pickle.loads(self.reader.read(length))

    def put_obj(self, obj: Any) -> None:
        """Write one object to the stream and flush it.

        Args:
            obj: Any picklable object. Objects of a class defined in the
                choreography are fine as long as both processes can import that
                class, which is automatic when every party runs the same
                program.

        Raises:
            pickle.PicklingError: If `obj` cannot be pickled.
        """
        data = pickle.dumps(obj)
        header = len(data).to_bytes(4,'big')
        self.writer.write(header)
        self.writer.write(data)
        self.writer.flush()  # important!

    def close(self) -> None:
        """Close the reader, the writer, and the underlying socket.

        Closing twice is harmless.
        """
        if self.sock is not None:
            self.writer.close()
            self.reader.close()
            self.sock.close()
            self.sock = None
            self.writer = None
            self.reader = None

    # Support for 'with' to close everything.

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

    # Support for no more references to ObjectStream

    def __del__(self):
        self.close()
