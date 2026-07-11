--------------------------------------------------------------------------------
                                      New
--------------------------------------------------------------------------------

* ARCOS
    * Added folder-based unittests for the ISIS parsers and made them raise
      SchemaEmptyParserError on empty output:
        * ShowIsisAdjacency, ShowIsisLsp, ShowIsisInterface, ShowIsisConfig,
          ShowIsisRoute, ShowIsisRedistributeRoute, ShowIsisGlobal,
          ShowIsisFastReroute, ShowIsisMicroLoopAvoidance,
          ShowIsisFlexAlgoFastReroute, ShowIsisFlexAlgoRoute,
          ShowIsisMplsLabelDb, ShowIsisLevelState, ShowIsisLevelCounters,
          ShowIsisSpfLog, ShowIsisGlobalTimers, ShowIsisProtectionTracker,
          ShowIsisGlobalTunnel
