#!/usr/bin/env python3
import argparse
import socketserver
import random
import threading
from dnslib import DNSRecord, DNSHeader, RR, A, QTYPE

# Colores ANSI para dar estilo a los logs
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
ELECTRIC_PINK = "\033[38;5;206m"



# Banner ASCII para PyRebinder
BANNER = f"""
{BLUE}{BOLD}
------------------------------------------------------------------------------
______________________________________________________________________________

██████╗ ██╗   ██╗██████╗ ███████╗██████╗ ██╗███╗   ██╗██████╗ ███████╗██████╗ 
██╔══██╗╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██║████╗  ██║██╔══██╗██╔════╝██╔══██╗
██████╔╝ ╚████╔╝ ██████╔╝█████╗  ██████╔╝██║██╔██╗ ██║██║  ██║█████╗  ██████╔╝
██╔═══╝   ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗██║██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗
██║        ██║   ██║  ██║███████╗██████╔╝██║██║ ╚████║██████╔╝███████╗██║  ██║
╚═╝        ╚═╝   ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝  

By bofill3
_______________________________________________________________________________
-------------------------------------------------------------------------------
{RESET}
"""

class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        try:
            request = DNSRecord.parse(data)
        except Exception as e:
            print(f"{YELLOW}[ERROR] Error parsing DNS request: {e}{RESET}")
            return

        print(f"{GREEN}[INFO] Received query from {self.client_address[0]}{RESET}")
        # Construye la respuesta DNS
        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
        qname = request.q.qname
        qtype = QTYPE[request.q.qtype]

        # Solo gestionamos consultas tipo A
        if qtype == "A":
            if self.server.mode == "random":
                ip_answer = random.choice(self.server.ips)
                log_mode = "random"
            elif self.server.mode == "roundrobin":
                with self.server.lock:
                    index = self.server.counter % len(self.server.ips)
                    ip_answer = self.server.ips[index]
                    self.server.counter += 1
                    log_mode = "roundrobin"
            elif self.server.mode == "count":
                with self.server.lock:
                    if self.server.counter < self.server.count_requests:
                        ip_answer = self.server.ips[0]
                    else:
                        ip_answer = self.server.ips[1]
                    self.server.counter += 1
                    log_mode = "count"
            else:
                ip_answer = random.choice(self.server.ips)
                log_mode = "default"
                
            print(f"{ELECTRIC_PINK}[INFO] Mode: {log_mode}. Responding with IP:{RESET} {ip_answer}{RESET}")
            reply.add_answer(RR(qname, rtype=QTYPE.A, rclass=1, ttl=self.server.ttl, rdata=A(ip_answer)))
        else:
            print(f"{MAGENTA}[WARN] Query type {qtype} not handled, sending empty response.{RESET}")

        sock.sendto(reply.pack(), self.client_address)

class ThreadedUDPServer(socketserver.ThreadingUDPServer):
    def __init__(self, server_address, handler_class, ips):
        self.ips = ips
        self.counter = 0
        self.lock = threading.Lock()
        super().__init__(server_address, handler_class)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="DNS server with configurable TTL, port and response mode."
    )
    parser.add_argument("--ips", required=True,
                        help="Comma-separated list of IP addresses to use in responses (e.g., '8.8.8.8,127.0.0.1').")
    parser.add_argument("--port", type=int, default=53,
                        help="Port to listen on (default: 53).")
    parser.add_argument("--ttl", type=int, default=0,
                        help="TTL value for DNS responses (default: 0).")
    parser.add_argument("--mode", choices=["random", "roundrobin", "count"], default="random",
                        help="Response mode: 'random', 'roundrobin' or 'count'.")
    parser.add_argument("--count-requests", type=int,
                        help="(Required for 'count' mode) Number of responses to serve with the first IP before switching.")
    args = parser.parse_args()

    # Procesa la lista de IPs eliminando espacios
    ips_list = [ip.strip() for ip in args.ips.split(",") if ip.strip()]

    # En modo 'count' se requieren exactamente 2 IPs y que se especifique el parámetro count-requests.
    if args.mode == "count":
        if len(ips_list) != 2:
            parser.error("count mode requires exactly 2 IP addresses.")
        if args.count_requests is None:
            parser.error("count mode requires --count-requests parameter.")

    # Imprime el banner al inicio
    print(BANNER)
    
    server = ThreadedUDPServer(('', args.port), DNSHandler, ips_list)
    server.mode = args.mode
    server.ttl = args.ttl
    if args.mode == "count":
        server.count_requests = args.count_requests

    print(f"{CYAN}[START] DNS server running on UDP port {args.port}{RESET}")
    print(f"{CYAN}[START] Mode: {args.mode}{RESET}")
    print(f"{CYAN}[START] Response IPs: {ips_list}{RESET}")
    print(f"{CYAN}[START] TTL: {args.ttl}{RESET}")
    if args.mode == "count":
        print(f"{CYAN}[START] count mode: first IP will be used for the first {args.count_requests} requests; then always the second IP.{RESET}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"{RED}[SHUTDOWN] Shutting down the server{RESET}")
        server.shutdown()
