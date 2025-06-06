# Advanced Networked Systems SS25

This repository contains code skeleton for the labs of Advanced Networked Systems SS25 at Paderborn University, Germany. There are in total three labs, which will be released one by one throughout the semester. For more details, please refer to the lab descriptions released on PANDA.

# start controller
vagrant up
vagrant ssh
ryu-manager /vagrant/lab1/ans_controller.py

# start topo
on 2nd terminal after VM ups
vagrant shh
sudo python3 run_network.py
mn -> exit
sudo mn -c

# to check flow table on perticular switch
one 3rd Terminal after vm up
vagrant shh
sudo ovs-ofctl dump-flows s1
sudo ovs-ofctl show s1

# to open xterm terminals
vagrant@ans-vm:~$ xterm -hold -e "sudo -E python3 /vagrant/lab1/run_network.py"
inside xterm open h1 h2 ser (assuming 10.0.0.2 is h2 IP)

| Goal      | h1 (client)                         | h2 (server)   |
| --------- | ----------------------------------- | ------------- |
| TCP test  | `iperf -c 10.0.0.2 -t 20`           | `iperf -s`    |
| UDP test  | `iperf -c 10.0.0.2 -u -t 20 -b 10M` | `iperf -s -u` |
| ICMP ping | `ping 10.0.0.2 -c 5`                | —             |



# ANS---Advanced-Network-System

## 📘 Fat-Tree Design Recap (k-ary Fat-Tree)

For a fat-tree with port count $k$:

| Component          | Formula                                                                                             | Example (k=4)  |
| ------------------ | --------------------------------------------------------------------------------------------------- | -------------- |
| **Pods**           | $k$                                                                                                 | 4              |
| **Core switches**  | $\left(\frac{k}{2}\right)^2$                                                                        | 4              |
| **Agg switches**   | $k \times \frac{k}{2} = \frac{k^2}{2}$                                                              | 8              |
| **Edge switches**  | $k \times \frac{k}{2} = \frac{k^2}{2}$                                                              | 8              |
| **Total switches** | $\frac{k^2}{2} + \frac{k^2}{2} + \left(\frac{k}{2}\right)^2 = k^2 + \frac{k^2}{4} = \frac{5k^2}{4}$ | 20 (for k=4)   |
| **Hosts**          | $\frac{k^3}{4}$                                                                                     | 16             |
| **Links**          | See below ↴                                                                                         | \~48 (for k=4) |

---

## 🔗 Link Count Details

A link is added:

1. Between each **edge switch** and $\frac{k}{2}$ hosts
   → Total: $\frac{k^2}{2} \times \frac{k}{2} = \frac{k^3}{4}$ (same as number of hosts)

2. Each **edge switch** connects to $\frac{k}{2}$ **agg switches** in the pod
   → Total: $\frac{k^2}{2} \times \frac{k}{2} = \frac{k^3}{4}$

3. Each **agg switch** connects to $\frac{k}{2}$ **core switches**
   → Total: $\frac{k^2}{2} \times \frac{k}{2} = \frac{k^3}{4}$

### 🔢 Total Links:

$$
\text{Total Links} = \frac{k^3}{4} + \frac{k^3}{4} + \frac{k^3}{4} = \frac{3k^3}{4}
$$

---

## ✅ Final Summary

| Component      | Formula          | Example (k=4) |
| -------------- | ---------------- | ------------- |
| Total Switches | $\frac{5k^2}{4}$ | 20            |
| Total Hosts    | $\frac{k^3}{4}$  | 16            |
| Total Links    | $\frac{3k^3}{4}$ | 48            |

---

## 🔁 For example, with **k = 6**:

| Component      | Value |
| -------------- | ----- |
| Total Switches | 45    |
| Total Hosts    | 54    |
| Total Links    | 162   |

let's h000 ping h101 (we know the namming pattern host already as per our fat tree)
(h000 - first pod first edge switch first host)
which IP of host is (10.p.s.h) where p- pod id, s- switch id, h - host id

so above case h000 first generate arp request which we to forward using dijkstra algo instead of floding pkt (h000 -> connected to 200 switch id) (h101 -> connected to 210 switch id) so using dijkstra first we'll find the shortest path(we'll go with first path)

but to use dijkstra algo we need src and target node id
(source node we know already where we received pkt and target node id we can create from dst ip)
(in our case h101 dst ip is 10.1.0.1) so we can get the target edge node id from it which is 210(2->edge, 1 pod number, 0 switch id)

just from above we'll get target edge path and we already have graph topo in which we have info about port so using that we can forward pkt till target edge and then we'll broad cast if its arp request, else if we already know dst ip mac connected on which port at target node then will simply forward pkt 

--------------

Perfect reasoning — you're now thinking **exactly like an SDN controller designer.** 👏

Let’s now **formalize** and **implement** this ARP-routing logic using Dijkstra — no flooding!

---

## 🧠 Recap Your Strategy (You’re Spot On)

1. **Host h000 (IP: 10.0.0.0)** pings **h101 (IP: 10.1.0.1)**.
2. The ARP request from `h000` must reach `h101`'s edge switch (e.g., `dpid = 210`).
3. Use destination IP (`10.1.0.1`) to compute target edge switch ID: `210`.
4. Run **Dijkstra from current switch to target edge switch**.
5. **Forward ARP packet hop by hop using the path and port info in `self.graph`**.
6. At the **final switch** (dpid `210`), either:

   * **Broadcast** the ARP (if we don’t yet know h101’s MAC).
   * **Unicast** to known MAC if already learned.

---

## ✅ IP to Edge Switch DPID Mapper Function

```python
def ip_to_edge_dpid(self, ip_str):
    # Example IP: 10.pod.switch.host
    try:
        parts = list(map(int, ip_str.split('.')))
        pod = parts[1]
        edge = parts[2]
        return int(f"2{pod}{edge}")  # matches our dpid scheme for edge switches
    except:
        return None
```

* `10.1.0.1` → pod = 1, edge = 0 → dpid = `210`
* `10.3.1.1` → dpid = `231`

---

## ✅ Update Your `_packet_in_handler()` to Route ARP via Dijkstra

### Add this block inside `if pkt.get_protocol(arp.arp)`:

```python
arp_pkt = pkt.get_protocol(arp.arp)
dst_ip = arp_pkt.dst_ip
dst_edge_dpid = self.ip_to_edge_dpid(dst_ip)

# Only handle ARP if we can determine the destination switch
if dst_edge_dpid is not None and dst_edge_dpid in self.graph:
    path = self.dijkstra(dpid, dst_edge_dpid)
    self.logger.info("ARP path %s → %s: %s", dpid, dst_edge_dpid, path)

    if len(path) >= 2:
        next_hop = path[1]
        out_port = self.graph[dpid][next_hop]
        actions = [parser.OFPActionOutput(out_port)]

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        )
        datapath.send_msg(out)
        return
```

Now instead of `flood`, the ARP request will travel **switch-by-switch** toward the destination edge switch (`210` in this case).

At the **final switch**:

* If the MAC of h101 is known: forward.
* If not: do **local flood** (inside that switch only).

---

## 🧠 Optional: Local ARP Flood at Target Edge

At dpid = 210, if `dst_mac` is not in `self.mac_location`, flood **only to hosts**:

```python
if dpid == dst_edge_dpid:
    for mac in self.graph[dpid]:
        if mac.startswith('00:00') and mac != src_mac:
            out_port = self.graph[dpid][mac]
            actions = [parser.OFPActionOutput(out_port)]
            ...
```

---

## ✅ Summary

| Step | What You Do                                              |
| ---- | -------------------------------------------------------- |
| 1    | Extract pod/switch from IP like `10.p.s.h`               |
| 2    | Convert to target edge switch dpid (e.g. `210`)          |
| 3    | Run Dijkstra from current dpid to target                 |
| 4    | Forward ARP packet along path using port info            |
| 5    | At final edge switch: broadcast to local hosts if needed |

---
