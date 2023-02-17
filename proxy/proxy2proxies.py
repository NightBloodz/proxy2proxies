import socket, threading, struct, select, random


class Proxy:

    def __init__(self, host, port, proxies, chain_n, tor):
        self.host = str(host)
        self.port = int(port)
        self.proxies = proxies
        self.chain_n = chain_n
        self.tor = tor
        self.version = 5

   
    def msg_loop(self, client, remote):
        """
        This method communicates both Client-side and Server-side sockets.

        Args:
            client (socket): Client-side socket.
            remote (socket): Server-side socket.
        """

        while True:
            try:
                #Wait until there is data to be read from either the client or the server.
                r, w, e = select.select([client, remote], [], [])


                #If the client sends data, send it to the server
                if client in r:
                    data = client.recv(4096)
                    if remote.send(data) <= 0:
                        break
                
                #If the server sends data, send it to the client
                if remote in r:
                    data = remote.recv(4096)
                    if client.send(data) <= 0:
                        break
            
            except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
                break
            

            
    def socks_negotiation(self, remote, target):
        """
        This method takes a created connection with a Socks5 proxy and negotiates with it in order to connect to the target.

        Args:
            remote (socket): The proxy socket created previously
            target (array):  The IP and the port of the proxy to connect
        """

        try:
            #First negotiation message, it contains (version (5), number of methods(1), method(no password))
            remote.sendall(b'\x05\x01\x00')

            #Get and handle the response
            response = remote.recv(2)
            if response != b'\x05\x00': 
                print("Negotiation with proxy failed")
                return "", remote

            
            #Convert the IP of the target to int format
            addr = struct.unpack("!I", socket.inet_aton(target[0]))[0]
            port = target[1]
            
            #Create the packet
            msg = struct.pack("!BBBBIH", self.version, 1, 0, 1, addr, port)
            remote.sendall(msg)
            
            #Get the response and return it to be handled after.
            response = remote.recv(10)

            return response, remote
        
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
            return "", remote

        
                 

    def chain_proxies(self, target):
        """
        This method creates a socket connection with the target through the specified proxies and returns it.

        Args:
            target (array): The IP and the port of the target to connect
        """
        
        chained = [] 
        
        #The chaining process has 50 tries.
        for i in range(0, 50):

            #Select a random proxy of the list
            proxy_n = random.randint(0, len(self.proxies)-1)
            proxy = self.proxies[proxy_n]

            #Check if the proxy is already chained
            if proxy in chained:
                continue

            
            try:
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.settimeout(15)

                 
                if self.chain_n == 0:
                #If the chain is set to 0, connect directly to the target
                    remote.connect((target[0], target[1]))
                    return remote
                else:
                #Connect with the First proxy
                    remote.connect((proxy[0], proxy[1]))


                #Chain proxies until the limit established in the variable chain_n
                while len(chained) < self.chain_n:

                    #Select a random proxy of the list
                    proxy_n = random.randint(0, len(self.proxies)-1)
                    proxy = self.proxies[proxy_n]

                    #Check if proxy is already chained
                    if proxy in chained:
                        continue
                    
                    
                    #Negotiate with the proxy using the Socks protocol in order to establish a connection to the target.
                    response, remote = self.socks_negotiation(remote, proxy)


                    #Check if the connection with the target succeeded.
                    if response[0:2] != b'\x05\x00':
                        continue
                        
                    #Append the new proxy to the chain list.
                    print("{} Chained successfully".format(proxy))
                    chained.append(proxy)
                
                #When all the proxies are Chained, connect the last connected proxy to the target.
                response, remote = self.socks_negotiation(remote, target)

                #If the response is successful, return the remote socket.
                if response[0:2] == b'\x05\x00':
                    print("Connected to target: {} successfully through proxies".format(target))
                    return remote                    



            except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
                chained = []
                print("Connection with the first proxy ended.")
                
                


        print("Limit of chaining trys exceeded")
        return False                                     


    
    

    def handle_client(self, client, addr):

        """
        This method takes the connection established with the client and handles it.
        
        Args:
            client (socket): Client-side socket
            addr 
        """

        bind_address = client.getsockname()
        
        #Recieve the header, it contains (socks version, number_of_methods, methods).
        #The client will send the header to specify the supported version and supported methods.
        
        version, n_methods = client.recv(2)

        #Server don't want auth, so it won't handle the methods
        methods = client.recv(n_methods)

        

        #Based on the client characteristics, the server will send (socks version, method to use) 
        #In this case, the server will send [5(socks5), 0(no authentication)]
        client.sendall(bytes([self.version, 0]))


        #The client won't send auth, instead, it will send the data of the remote host to connect.
        #The packet will contain [version, conn_type, _, address_type(ip, Domain...), target_addr, target_port]
        #First, the server will get only 4 bytes and save them in 4 variables.
        version, conn_type, _, address_type = client.recv(4)

        if address_type == 1: #ip
        #address_type 1 --> ip --> recv 4 bytes and convert to ip str
            address = socket.inet_ntoa(client.recv(4))

        elif address_type == 3: #domain
        #address_type 3 --> domain --> recv 1 byte to get the lenght of the domain --> recv the domain
            domain_length = ord(client.recv(1))
            address = client.recv(domain_length).decode()
            address = socket.gethostbyname(address)

        elif address_type == 4: #ipv6
            client.close()
            return False                #TODO

        else:
            client.close()
            return False
            
        
    
        
        #Recv 2 bytes and convert them to port
        port = client.recv(2)
        port = struct.unpack('>H', port)[0]

        target = [address, port]
            

        #Connect to target
        if conn_type == 1: #Connect using TCP

            #Establish TCP connection with target through chained proxies
            #Chain all the proxies and connect to the target
            remote = self.chain_proxies(target)

            #Store the status of the connection in a packet
            if remote:
                #Convert the bind_ip to int format
                addr = struct.unpack("!I", socket.inet_aton(bind_address[0]))[0]
                port = bind_address[1]
                reply = struct.pack("!BBBBIH", self.version, 0, 0, 1, addr, port)
            else:
                reply = struct.pack("!BBBBIH", self.version, 5, 0, 1, 0, 0)

        else: 
            print("Connection closed (conn_type)")
            client.close()
        

        #Server sends the status packet 
        client.sendall(reply)
       

        #if both connection succeed, the client and target can start comunicating.
        if reply[1] == 0 and conn_type == 1:
            print("client: {} connected to server: {}".format(target[0], target[1]))
            self.msg_loop(client, remote)
        else:
            print("Connection to target: {} failed".format(target[0]))

        

        client.close()
        print("Connection with client ended")
        
                   


    def run(self):
        
        #Create the server socket
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.bind((self.host, self.port))
        srv_sock.listen(5)
        
        while True:
            #Accept a client connection.
            conn, addr = srv_sock.accept()

            #Pass the connection data to the handle_client function in order to handle the connection.
            c = threading.Thread(target=self.handle_client, args=(conn, addr))
            c.start()

            print("New connection with client: " + str(addr))
   

