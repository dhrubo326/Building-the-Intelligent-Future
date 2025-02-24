import socket
import struct
import threading

# Constants
HEADER_SIZE = 4  # Match server's header size

def receive_messages(sock):
    """Handle incoming messages from the server."""
    buffer = b''
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                print("\nConnection closed by server.")
                break
            buffer += data
            
            # Process all complete messages in buffer
            while len(buffer) >= HEADER_SIZE:
                header = buffer[:HEADER_SIZE]
                (msg_length,) = struct.unpack("!I", header)
                
                if len(buffer) >= HEADER_SIZE + msg_length:
                    message = buffer[HEADER_SIZE:HEADER_SIZE + msg_length]
                    print(message.decode('utf-8'))
                    # Remove processed message from buffer
                    buffer = buffer[HEADER_SIZE + msg_length:]
                else:
                    break  # Wait for more data
        except ConnectionResetError:
            print("\nConnection lost with server")
            break
        except Exception as e:
            # print(f"\nError receiving data: {e}")
            break
    sock.close()

def start_client():
    """Initialize and run the chat client."""
    server_ip = input("Enter server IP: ")
    # server_ip = socket.gethostbyname(socket.gethostname())
    server_port = int(input("Enter server port [6677]: ") or 6677)
    # server_port = 6677
    username = input("Choose a username: ")

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_sock.connect((server_ip, server_port))
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # Send username first
    try:
        username_encoded = username.encode('utf-8')
        header = struct.pack("!I", len(username_encoded))
        client_sock.sendall(header + username_encoded)
    except Exception as e:
        print(f"Failed to send username: {e}")
        client_sock.close()
        return

    # Check for username rejection
    try:
        # Wait briefly for server response
        client_sock.settimeout(2)
        header = client_sock.recv(HEADER_SIZE)
        if header:
            msg_length = struct.unpack("!I", header)[0]
            error_msg = client_sock.recv(msg_length).decode('utf-8')
            print(f"Server response: {error_msg}")
            client_sock.close()
            return
    except socket.timeout:
        pass  # No error message means username accepted
    except Exception as e:
        print(f"Error checking username: {e}")
        client_sock.close()
        return
    finally:
        client_sock.settimeout(None)

    print(f"Connected to chat! Type messages below (type '/exit' to quit)")

    # Start receiver thread
    receiver_thread = threading.Thread(
        target=receive_messages, 
        args=(client_sock,),
        daemon=True
    )
    receiver_thread.start()

    # Handle user input
    try:
        while True:
            message = input()
            if message.lower() == '/exit':
                break
            
            try:
                message_encoded = message.encode('utf-8')
                header = struct.pack("!I", len(message_encoded))
                client_sock.sendall(header + message_encoded)
            except Exception as e:
                # print(f"Failed to send message: {e}")
                break
    finally:
        client_sock.close()

if __name__ == '__main__':
    start_client()