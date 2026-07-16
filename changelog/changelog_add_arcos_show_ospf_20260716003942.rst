--------------------------------------------------------------------------------
                                      New
--------------------------------------------------------------------------------

* ARCOS
    * Added folder-based unittests for the OSPF/OSPFv3 parsers and made them
      raise SchemaEmptyParserError on empty output:
        * ShowOspfGlobal, ShowOspfNeighbor, ShowOspfArea, ShowOspfInterface,
          ShowOspfSpfThrottle, ShowOspfLsdb, ShowOspfRunningConfig,
          ShowOspfv3RunningConfig
