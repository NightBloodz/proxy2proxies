import socket, threading, struct, select, random


class Proxy:

    def __init__(self, host, port, proxies, chain_n, tor):
        self.host = str(host)
        self.port = int(port)
        self.proxies = proxies
        self.chain_n = chain_n
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
                

    def socks_negotiation(self, remote, target):
                
        #First negotiation_message
        remote.sendall(b'\x05\x01\x00')

        response = remote.recv(2)
        if response != b'\x05\x00':
            print("Negotiation with proxy failed")
            return "", remote

        
        addr = struct.unpack("!I", socket.inet_aton(target[0]))[0]
        port = target[1]
        
        msg = struct.pack("!BBBBIH", self.version, 1, 0, 1, addr, port)
        remote.sendall(msg)
        
        response = remote.recv(10)

        return response, remote
        
                 

    def chain_proxies(self, target, client):
        
        
        chained = [] 
        
        for i in range(0, 200):

            #Select a random proxy of the list
            proxy_n = random.randint(0, len(self.proxies)-1)
            proxy = self.proxies[proxy_n]

            #Check if proxy is already chained
            if proxy in chained:
                continue

            try:
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.settimeout(15)

                 
                if self.chain_n == 0:
                    #If the chain is set to 0 connect directly to target
                    remote.connect((target[0], target[1]))
                    return remote
                else:
                    #Connect with the First proxy
                    remote.connect((proxy[0], proxy[1]))

                #Chain proxies until the limit established in chain_n
                #Negotiate with socks and connect to the restant proxies
                while len(chained) < self.chain_n:
                    #Select a random proxy of the list
                    proxy_n = random.randint(0, len(self.proxies)-1)
                    proxy = self.proxies[proxy_n]
                    #Check if proxy is already chained
                    if proxy in chained:
                        continue
                    
                    response, remote = self.socks_negotiation(remote, proxy)

                    #Check if the connection with target succeeded and append the new proxy to chained list
                    if response[0:2] != b'\x05\x00':
                        continue
                        
                    print("{} Chained successfully".format(proxy))
                    chained.append(proxy)
                
                #When all the proxies are Chained connect the last proxy with the target
                response, remote = self.socks_negotiation(remote, target)

                #If the response is successful, return the remote value of the connection.
                if response[0:2] == b'\x05\x00':
                    print("Connected to target: {} successfully through proxies".format(target))
                    return remote                    



            except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
                chained = []
                print("Connection with the first proxy ended.")
                
                


        print("Limit of chaining trys exceeded")
        return False                                     


    
    

    def handle_client(self, client, addr):

        bind_address = client.getsockname()

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
            

        #Connect to target regarding conn_type
        if conn_type == 1: #Connect using TCP
            #Establish TCP connection with target through random selected chained proxies
            #Chain all the proxies and connect to the target
            remote = self.chain_proxies(target, client)

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
       


        #if both connection succeed, the client and target can start comunicating
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
        srv_sock.listen(100)
        
        while True:
            #Accept a client connection.
            conn, addr = srv_sock.accept()

            #Pass the connection data to the handle_client function in a new thread to handle the client's connection
            c = threading.Thread(target=self.handle_client, args=(conn, addr))
            c.start()
            


            print("New connection with client: " + str(addr))
   

