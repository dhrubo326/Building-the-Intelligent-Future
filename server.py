import socket
import struct
import selectors
from collections import defaultdict

# Constants
HOST = socket.gethostbyname(socket.gethostname())
# PORT = 6677
PORT = int(input("Enter server port [6677]: ") or 6677)
HEADER_SIZE = 4  # Bytes to store message length
sel = selectors.DefaultSelector()

# Store client data: {socket: {'buffer': b'', 'state': '...', 'username': '...'}}
clients = {}

def send_message(sock, message):
    """Send a message to a client with proper framing."""
    try:
        message_encoded = message.encode('utf-8')
        header = struct.pack("!I", len(message_encoded))
        sock.sendall(header + message_encoded)
    except Exception as e:
        print(f"Error sending message: {e}")
        disconnect_client(sock)

def broadcast(message, sender_sock=None):
    """Broadcast message to all connected clients except sender."""
    for client in list(clients.keys()):
        if client != sender_sock:
            try:
                header = struct.pack("!I", len(message))
                client.sendall(header + message)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnect_client(client)

def disconnect_client(sock):
    """Cleanup client connection and notify other users."""
    if sock in clients:
        client_data = clients[sock]
        username = client_data['username']
        
        if username:
            leave_msg = f"\033[5;91m\t* {username} has left the chat *\033[0m".encode('utf-8')
            broadcast(leave_msg, sock)
            print(f"User '{username}' disconnected")

        sel.unregister(sock)
        sock.close()
        del clients[sock]

def handle_client_initialization(sock, client_data):
    """Handle username negotiation during client connection."""
    buffer = client_data['buffer']
    
    if client_data['state'] == 'awaiting_username_header':
        if len(buffer) >= HEADER_SIZE:
            header = buffer[:HEADER_SIZE]
            buffer = buffer[HEADER_SIZE:]
            (username_len,) = struct.unpack("!I", header)
            
            client_data.update({
                'state': 'awaiting_username',
                'expected_len': username_len,
                'buffer': buffer
            })

    elif client_data['state'] == 'awaiting_username':
        if len(buffer) >= client_data['expected_len']:
            username = buffer[:client_data['expected_len']].decode('utf-8')
            buffer = buffer[client_data['expected_len']:]
            
            # Check for existing username
            if any(c['username'] == username for c in clients.values() if c['username']):
                send_message(sock, "ERROR: Username already taken")
                disconnect_client(sock)
                return

            client_data.update({
                'state': 'ready',
                'username': username,
                'buffer': buffer
            })
            
            print(f"User '{username}' joined the chat")
            welcome_msg = f"\033[5;91m\t* {username} has joined the chat *\033[0m".encode('utf-8')
            broadcast(welcome_msg, sock)
            
            # Process any remaining data in buffer
            if len(buffer) > 0:
                handle_client_messages(sock, client_data)

def handle_client_messages(sock, client_data):
    """Process complete messages in client buffer."""
    buffer = client_data['buffer']
    
    while True:
        if len(buffer) < HEADER_SIZE:
            break

        # Extract message length
        header = buffer[:HEADER_SIZE]
        (msg_len,) = struct.unpack("!I", header)
        
        if len(buffer) < HEADER_SIZE + msg_len:
            break

        # Process complete message
        message = buffer[HEADER_SIZE:HEADER_SIZE + msg_len].decode('utf-8')
        buffer = buffer[HEADER_SIZE + msg_len:]
        
        # Update buffer and handle message
        client_data['buffer'] = buffer
        formatted = f"\033[1;92m\t{client_data['username']}: {message}\033[0m".encode('utf-8')
        print(formatted.decode('utf-8'))
        broadcast(formatted, sock)

def handle_client(sock, mask):
    """Main client connection handler."""
    client_data = clients.get(sock)
    if not client_data:
        return

    try:
        if mask & selectors.EVENT_READ:
            # Read available data
            data = sock.recv(4096)
            if not data:
                raise ConnectionError("Client disconnected")
            
            client_data['buffer'] += data

            # State machine
            if client_data['state'] != 'ready':
                handle_client_initialization(sock, client_data)
            else:
                handle_client_messages(sock, client_data)

    except Exception as e:
        print(f"Client error: {e}")
        disconnect_client(sock)

def accept_connection(sock, mask):
    """Accept new connections and initialize client state."""
    client_sock, addr = sock.accept()
    print(f"New connection from {addr}")
    
    client_sock.setblocking(False)
    clients[client_sock] = {
        'buffer': b'',
        'state': 'awaiting_username_header',
        'username': None
    }
    
    sel.register(client_sock, selectors.EVENT_READ, handle_client)

def start_server():
    """Initialize and run the chat server."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()
    server_sock.setblocking(False)
    
    sel.register(server_sock, selectors.EVENT_READ, accept_connection)
    print(f"Server started on {HOST}:{PORT}")

    try:
        while True:
            events = sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    finally:
        for sock in list(clients.keys()):
            disconnect_client(sock)
        sel.close()
        server_sock.close()

if __name__ == '__main__':
    start_server()