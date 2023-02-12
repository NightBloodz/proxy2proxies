import socket, threading, struct, select


class Proxy:

    def __init__(self, host, port, proxies, tor):
        self.host = str(host)
        self.port = int(port)
        self.proxies = proxies
        self.tor = tor
        self.version = 5


    def msg_loop(self, conn, remote):

        while True: 
            #Whait until there are data to read for client or server
            r, w, e = select.select([conn, remote], [], [])

            if conn in r:
                data = conn.recv(4096)
                if remote.send(data) <= 0:
                    break

            if remote in r:
                data = remote.recv(4096)
                if conn.send(data) <= 0:
                    break
                

    def connect_2_server(self, conn_type, target, client):
        try:
            #Connect to target regarding conn_type
            if conn_type == 1: #Connect
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.connect((target[0], target[1]))

                #Get ip and port of the socket
                bind_address = remote.getsockname()
            
            else: 
                print("Connection closed (conn_type)")
                client.close()
                


            #The server creates the packet to comunicate the success of the target connection.
            #The packet contains (version, rep_status, _, addr_type(ip), bind_addr, bind_port)
            
            #First convert the ip to byte format and then to int format
            addr = struct.unpack("!I", socket.inet_aton(bind_address[0]))[0]
            port = bind_address[1]

            reply = struct.pack("!BBBBIH", self.version, 0, 0, 1, addr, port)
        

        except Exception as err:
            #Create the packet to comunicate the failure.
            #The packet contains (version, error_code, _, addr_type(failure), bind_addr(failure), bnd_port(failure))
            reply = struct.pack("!BBBBIH", self.version, 5, 0, 0, 0, 0)

        
        #return the reply and the remote connection
        return reply, remote
                 



    def handle_client(self, client, addr):
        #Recieve the header, it contains (socks version, number_of_methods, methods).
        #The client will send the header to specify the supported version and supported methods.
        #Server don't want auth, so it won't save the methods
        client.recv(3)

        #Regarding the client characteristics, the server will send (socks version, method2use) 
        #In this case, the server will send [5(socks5), 0(no authentication)]
        client.sendall(bytes([self.version, 0]))

        #The client won't send auth, instead It will send the data of the remote host to connect
        #The packet will contain [version, conn_type, _, address_type(ip, Domain...), target_addr, target_port]
        #First, server will get only 4 bytes to get the first 4 variables
        version, conn_type, _, address_type = client.recv(4)

        if address_type == 1: #ip
        #address_type 1 --> ip --> recv 4 bytes and convert to ip str
            address = socket.inet_ntoa(client.recv(4))

        elif address_type == 3: #domain
        #address_type 3 --> domain --> recv 1 byte to get the lenght of the domain --> recv the domain
            domain_length = ord(client.recv(1))
            address = client.recv(domain_length).decode()

        elif address_type == 4: #ipv6
            pass                #TODO
            
        #Recv 2 bytes and convert them to port
        port = client.recv(2)
        port = struct.unpack('>H', port)[0]

        target = [address, port]


        reply, remote = self.connect_2_server(conn_type, target, client)


        #Server sends the packet 
        client.sendall(reply)
       


        #if both connection succeed, the client and target can start comunicating
        if reply[1] == 0 and conn_type == 1:
            print("client: {} connected to server: {}".format(addr, target[0]))
            self.msg_loop(client, remote)
        else:
            print("Connection to target: {} failed".format(target[0]))

        

        client.close()
        print("Connection to target: {} ended".format(target[0]))
        
        


                




    def run(self):
        
        #Create the server socket
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.bind((self.host, self.port))
        srv_sock.listen(100)
        
        while True:
            #Accept a client connection.
            conn, addr = srv_sock.accept()

            #Pass the connection data to the handle_client function in a new thread to handle the client's connection
            c = threading.Thread(target=self.handle_client, args=(conn, addr))
            c.start()

            print("New connection with client: " + str(addr))

        
        

if __name__ == '__main__':
    proxy = Proxy("0.0.0.0", 3000, proxies=False, tor=False)
    proxy.run()