containernet> ue1 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.45.0.2/16 fe80::1b9c:10ae:66ba:4770/64 
containernet> ue2 ip -br addr show uesimtun0
uesimtun0        UNKNOWN        10.46.0.2/16 fe80::d8:12ef:8181:e32b/64 
containernet> ue1 ping -I uesimtun0 -c 3 10.45.0.1
PING 10.45.0.1 (10.45.0.1) from 10.45.0.2 uesimtun0: 56(84) bytes of data.
64 bytes from 10.45.0.1: icmp_seq=1 ttl=64 time=1.05 ms
64 bytes from 10.45.0.1: icmp_seq=2 ttl=64 time=0.699 ms
64 bytes from 10.45.0.1: icmp_seq=3 ttl=64 time=0.781 ms

--- 10.45.0.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2028ms
rtt min/avg/max/mdev = 0.699/0.841/1.045/0.147 ms
containernet> ue1 iperf3 -c 10.45.0.1 -B 10.45.0.2 -t 15
Connecting to host 10.45.0.1, port 5201
[  5] local 10.45.0.2 port 45291 connected to 10.45.0.1 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-1.00   sec  2.75 MBytes  23.1 Mbits/sec  281   10.5 KBytes       
[  5]   1.00-2.00   sec  1.23 MBytes  10.4 Mbits/sec  142   11.8 KBytes       
[  5]   2.00-3.00   sec  1.54 MBytes  12.9 Mbits/sec  155   5.27 KBytes       
[  5]   3.00-4.00   sec   948 KBytes  7.76 Mbits/sec  107   7.90 KBytes       
[  5]   4.00-5.00   sec  1.54 MBytes  12.9 Mbits/sec  155   7.90 KBytes       
[  5]   5.00-6.00   sec  1.23 MBytes  10.4 Mbits/sec  124   2.63 KBytes       
[  5]   6.00-7.00   sec  1.23 MBytes  10.4 Mbits/sec  135   15.8 KBytes       
[  5]   7.00-8.00   sec  1.23 MBytes  10.4 Mbits/sec  110   18.4 KBytes       
[  5]   8.00-9.00   sec  1.23 MBytes  10.4 Mbits/sec   86   6.58 KBytes       
[  5]   9.00-10.00  sec  1.54 MBytes  12.9 Mbits/sec  118   13.2 KBytes       
[  5]  10.00-11.00  sec   948 KBytes  7.76 Mbits/sec  117   6.58 KBytes       
[  5]  11.00-12.00  sec  1.23 MBytes  10.4 Mbits/sec  111   13.2 KBytes       
[  5]  12.00-13.00  sec  1.54 MBytes  12.9 Mbits/sec  138   26.3 KBytes       
[  5]  13.00-14.00  sec  1.23 MBytes  10.4 Mbits/sec  125   3.95 KBytes       
[  5]  14.00-15.00  sec  1.23 MBytes  10.4 Mbits/sec  147   5.27 KBytes       
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-15.00  sec  20.6 MBytes  11.5 Mbits/sec  2051             sender
[  5]   0.00-15.09  sec  20.0 MBytes  11.1 Mbits/sec                  receiver

iperf Done.
containernet> ue2 iperf3 -c 10.46.0.1 -B 10.46.0.2 -t 15
Connecting to host 10.46.0.1, port 5201
[  5] local 10.46.0.2 port 51755 connected to 10.46.0.1 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-1.00   sec  1.42 MBytes  11.9 Mbits/sec  229   2.63 KBytes       
[  5]   1.00-2.00   sec   316 KBytes  2.59 Mbits/sec   78   2.63 KBytes       
[  5]   2.00-3.00   sec   632 KBytes  5.18 Mbits/sec   59   2.63 KBytes       
[  5]   3.00-4.00   sec   316 KBytes  2.59 Mbits/sec   46   3.95 KBytes       
[  5]   4.00-5.00   sec   316 KBytes  2.59 Mbits/sec   56   2.63 KBytes       
[  5]   5.00-6.00   sec   632 KBytes  5.18 Mbits/sec   39   1.32 KBytes       
[  5]   6.00-7.00   sec   316 KBytes  2.59 Mbits/sec   42   1.32 KBytes       
[  5]   7.00-8.00   sec   316 KBytes  2.59 Mbits/sec   50   1.32 KBytes       
[  5]   8.00-9.00   sec   632 KBytes  5.18 Mbits/sec   43   1.32 KBytes       
[  5]   9.00-10.00  sec   316 KBytes  2.59 Mbits/sec   58   3.95 KBytes       
[  5]  10.00-11.00  sec   316 KBytes  2.59 Mbits/sec   46   3.95 KBytes       
[  5]  11.00-12.00  sec   632 KBytes  5.18 Mbits/sec   51   3.95 KBytes       
[  5]  12.00-13.00  sec   316 KBytes  2.59 Mbits/sec   41   2.63 KBytes       
[  5]  13.00-14.00  sec   632 KBytes  5.18 Mbits/sec   55   1.32 KBytes       
[  5]  14.00-15.00  sec   316 KBytes  2.59 Mbits/sec   42   2.63 KBytes       
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-15.00  sec  7.29 MBytes  4.07 Mbits/sec  935             sender
[  5]   0.00-15.08  sec  6.62 MBytes  3.68 Mbits/sec                  receiver

iperf Done.
containernet> ue1 ping -I uesimtun0 -c 5 10.46.0.2
PING 10.46.0.2 (10.46.0.2) from 10.45.0.2 uesimtun0: 56(84) bytes of data.

--- 10.46.0.2 ping statistics ---
5 packets transmitted, 0 received, 100% packet loss, time 4075ms

containernet> ue1 ip route add 10.33.33.0/24 via 10.34.0.2
containernet> ue1 ping -c 3 10.33.33.9
PING 10.33.33.9 (10.33.33.9) 56(84) bytes of data.

--- 10.33.33.9 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2079ms

containernet> ue1 ip route del 10.33.33.0/24 via 10.34.0.2
containernet> 


