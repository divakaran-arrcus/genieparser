--------------------------------------------------------------------------------
                            New
--------------------------------------------------------------------------------
* ARCOS
    * Added ShowIsisAdjacency:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level} adjacency
    * Added ShowIsisLsp:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} link-state-database lsp
    * Added ShowIsisInterface:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} interface
    * Added ShowIsisConfig:
        * show running-config network-instance {network_instance} protocol ISIS {protocol_instance}
    * Added ShowIsisRoute:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route {prefix}
    * Added ShowIsisRedistributeRoute:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST redistribute-route
    * Added ShowIsisGlobal:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global state
    * Added ShowIsisFastReroute:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST fast-reroute
    * Added ShowIsisMicroLoopAvoidance:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global micro-loop-avoidance
    * Added ShowIsisFlexAlgoFastReroute:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} fast-reroute
    * Added ShowIsisFlexAlgoRoute:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} route
    * Added ShowIsisMplsLabelDb:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global mpls
    * Added ShowIsisLevelState:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} state
    * Added ShowIsisLevelCounters:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} system-level-counters
    * Added ShowIsisSpfLog:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global spf-log
    * Added ShowIsisGlobalTimers:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global timers
    * Added ShowIsisProtectionTracker:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global protection-tracker
    * Added ShowIsisGlobalTunnel:
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global tunnel
        * show network-instance {network_instance} protocol ISIS {protocol_instance} global tunnel {tunnel_id}
    * Added ShowBgpNeighbor:
        * show network-instance {network_instance} protocol BGP {protocol_instance} neighbor
        * show network-instance {network_instance} protocol BGP {protocol_instance} neighbor {neighbor}
    * Added ShowBgpGlobalState:
        * show network-instance {network_instance} protocol BGP {protocol_instance} global state
    * Added ShowBgpGlobalAfiSafi:
        * show network-instance {network_instance} protocol BGP {protocol_instance} global afi-safi
    * Added ShowBgpRibRoute:
        * show network-instance {network_instance} protocol BGP {protocol_instance} rib afi-safi {afi_safi} loc-rib route
        * show network-instance {network_instance} protocol BGP {protocol_instance} rib afi-safi {afi_safi} loc-rib route {prefix}
    * Added ShowBgpConfig:
        * show running-config network-instance {network_instance} protocol BGP
    * Added ShowBgpLabelDb:
        * show network-instance {ni} protocol BGP {instance} global mpls label-db
    * Added ShowBgpDeaggregationLabel:
        * show network-instance * protocol BGP * global afi-safi * state deaggregation-label
    * Added ShowBgpVpnExportedRoutes:
        * show network-instance default protocol BGP default rib afi-safi {afi_safi} network-instance {vrf_name} exported-rib route
    * Added ShowOspfGlobal:
        * show network-instance {ni} protocol OSPF {instance} global state
    * Added ShowOspfNeighbor:
        * show network-instance {ni} protocol OSPF {instance} area {area} interface * neighbor
    * Added ShowOspfArea:
        * show network-instance {ni} protocol OSPF {instance} area state
    * Added ShowOspfInterface:
        * show network-instance {ni} protocol OSPF {instance} area {area} interface state
    * Added ShowOspfSpfThrottle:
        * show network-instance {ni} protocol OSPF {instance} global spf throttle
    * Added ShowOspfLsdb:
        * show network-instance {ni} protocol OSPF {instance} area {area} lsdb
    * Added ShowOspfRunningConfig:
        * show running-config network-instance {ni} protocol OSPF {instance}
    * Added ShowOspfGlobalRib:
        * show network-instance {ni} protocol OSPF {instance} global rib prefix
    * Added ShowOspfv3Global:
        * show network-instance {ni} protocol OSPF3 {instance} global state
    * Added ShowOspfv3Neighbor:
        * show network-instance {ni} protocol OSPF3 {instance} area {area} interface * neighbor
    * Added ShowOspfv3RunningConfig:
        * show running-config network-instance {ni} protocol OSPF3 {instance}
    * Added ShowOspfv3Area:
        * show network-instance {ni} protocol OSPF3 {instance} area {area} state
    * Added ShowOspfv3Interface:
        * show network-instance {ni} protocol OSPF3 {instance} area {area} interface state
    * Added ShowOspfv3SpfThrottle:
        * show network-instance {ni} protocol OSPF3 {instance} global spf throttle
    * Added ShowOspfv3Lsdb:
        * show network-instance {ni} protocol OSPF3 {instance} area {area} lsdb
    * Added ShowOspfv3GlobalRib:
        * show network-instance {ni} protocol OSPF3 {instance} global rib prefix
    * Added ShowInterface:
        * show interface
        * show interface {interface}
    * Added ShowEvpn:
        * show evpn
    * Added ShowEvpnState:
        * show evpn state router-ip-selected
    * Added ShowEvpnEsiInfo:
        * show evpn esi-info esi
    * Added ShowL2ribMacEntries:
        * show network-instance {ni} l2rib mac-entries
    * Added ShowEvpnVpws:
        * show network-instance default protocol BGP default global afi-safi L2VPN_EVPN vpws
    * Added ShowL2ribVpwsEviEntries:
        * show network-instance {ni} l2rib vpws-evi-entries
    * Added ShowLdpInterface:
        * show network-instance default mpls signaling-protocols ldp interface-attributes interface
    * Added ShowLdpSession:
        * show network-instance default mpls signaling-protocols ldp sessions ipv4 session
    * Added ShowLdpHelloAdjacency:
        * show network-instance default mpls signaling-protocols ldp hello-adjacencies ipv4 hello-adjacency
    * Added ShowLdpNeighbor:
        * show network-instance default mpls signaling-protocols ldp neighbor
    * Added ShowSrmsMappingsConfig:
        * show running-config network-instance {instance} segment-routing
    * Added ShowSrPolicySegmentList:
        * show network-instance default sr-policy segment-list
    * Added ShowSrPolicyPolicy:
        * show network-instance default sr-policy policy
    * Added ShowSrPolicyDatabasePolicy:
        * show network-instance default sr-policy database policy
    * Added ShowSrv6Config:
        * show running-config network-instance {instance} srv6
    * Added ShowSrv6Locator:
        * show network-instance {instance} srv6 locator
        * show network-instance {instance} srv6 locator {locator_name}
    * Added ShowSrv6LocalSids:
        * show network-instance {instance} srv6 local-sids
    * Added ShowRsvpGlobal:
        * show network-instance {ni} protocol RSVP {instance} global state
    * Added ShowTeAdminGroup:
        * show network-instance {network_instance} te admin-group
    * Added ShowMplsReservedLabelBlockConfig:
        * show running-config network-instance {network_instance} mpls global reserved-label-block
    * Added ShowMplsReservedLabelBlock:
        * show network-instance {network_instance} mpls global reserved-label-block
    * Added ShowRibEntries:
        * show network-instance {network_instance} rib {af} ipv4-entries
        * show network-instance {network_instance} rib {af} ipv4-entries entry {prefix}
        * show network-instance {network_instance} rib {af} ipv6-entries
        * show network-instance {network_instance} rib {af} ipv6-entries entry {prefix}
    * Added ShowRibLabelEntries:
        * show network-instance {network_instance} rib {af} ipv4-label-entries
        * show network-instance {network_instance} rib {af} ipv4-label-entries entry {label}
        * show network-instance {network_instance} rib {af} ipv6-label-entries
        * show network-instance {network_instance} rib {af} ipv6-label-entries entry {label}
    * Added ShowFibPrefixEntries:
        * show network-instance {network_instance} fib {af} ipv4-prefix-entry
        * show network-instance {network_instance} fib {af} ipv4-prefix-entry {prefix}
        * show network-instance {network_instance} fib {af} ipv6-prefix-entry
        * show network-instance {network_instance} fib {af} ipv6-prefix-entry {prefix}
    * Added ShowFibNexthopEntries:
        * show network-instance {network_instance} fib {af} ipv4-nexthop-entry
        * show network-instance {network_instance} fib {af} ipv4-nexthop-entry {index}
        * show network-instance {network_instance} fib {af} ipv6-nexthop-entry
        * show network-instance {network_instance} fib {af} ipv6-nexthop-entry {index}
    * Added ShowFibLabelEntries:
        * show network-instance {network_instance} fib {af} ipv4-label-entry
        * show network-instance {network_instance} fib {af} ipv4-label-entry {label}
        * show network-instance {network_instance} fib {af} ipv6-label-entry
        * show network-instance {network_instance} fib {af} ipv6-label-entry {label}
    * Added ShowStaticRoutingConfig:
        * show running-config network-instance {network_instance} protocol STATIC {protocol_instance}
    * Added ShowStaticVxlanTunnels:
        * show overlay static-vxlan-tunnels
    * Added ShowRoutingPolicyDefinedSets:
        * show routing-policy defined-sets
    * Added ShowRoutingPolicyPolicyDefinition:
        * show routing-policy policy-definition
    * Added ShowRoutingPolicyConfig:
        * show running-config routing-policy
    * Added ShowNetworkInstance:
        * show network-instance {network_instance}
    * Added ShowAclSet:
        * show acl acl-set {name} {acl_type}
        * show acl acl-set
    * Added ShowQosPolicy:
        * show qos policy {name}
        * show qos policy
    * Added ShowCoppPolicy:
        * show copp policy {name}
    * Added ShowBfd:
        * show bfd
    * Added ShowVrrp:
        * show interface {interface} subinterface {sub_id} {af} address {address} vrrp
    * Added ShowVlan:
        * show vlan
    * Added ShowStpGlobal:
        * show stp global
    * Added ShowLacpInterface:
        * show lacp interface {bond}
        * show lacp interface
    * Added ShowLldpState:
        * show lldp state
    * Added ShowLldpInterface:
        * show lldp interface {interface}
        * show lldp interface
    * Added ShowStormControl:
        * show interface {interface} storm-control
    * Added ShowPortSecurity:
        * show port-security
    * Added ShowBridgeIsolation:
        * show interface {interface} bridge-isolation
    * Added ShowDamping:
        * show interface {interface} damping
    * Added ShowKeychainConfig:
        * show running-config keychain | display json | nomore
        * show running-config keychain {name} | display json | nomore
    * Added ShowKeychain:
        * show keychain | display json | nomore
        * show keychain {name} | display json | nomore
    * Added ShowNatInstance:
        * show nat instance {instance_id}
    * Added ShowDhcpRelay:
        * show relay-agent dhcp
    * Added ShowIpsecConnEntry:
        * show ipsec-ike conn-entry {name}
    * Added ShowIpfix:
        * show ipfix
    * Added ShowSflow:
        * show sflow
    * Added ShowSlaIcmp:
        * show network-instance {ni} sla icmp
    * Added ShowSynce:
        * show operational-state sync-e
    * Added ShowPtpInstance:
        * show ptp instance-list {instance_id} clock-info
    * Added ShowMonitorSession:
        * show monitor-session
    * Added ShowSnmpServer:
        * show system snmp-server enable
    * Added ShowGnmiServer:
        * show system grpc-server
    * Added ShowTelemetry:
        * show telemetry-system
    * Added ShowNtp:
        * show system ntp
    * Added ShowSystemHostname:
        * show system hostname
    * Added ShowVersion:
        * show version
