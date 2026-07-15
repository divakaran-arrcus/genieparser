--------------------------------------------------------------------------------
                                      New
--------------------------------------------------------------------------------

* ARCOS
    * Added folder-based unittests for the BGP parsers and made them raise
      SchemaEmptyParserError on empty output:
        * ShowBgpNeighbor, ShowBgpGlobalState, ShowBgpGlobalAfiSafi,
          ShowBgpRibRoute, ShowBgpConfig, ShowBgpLabelDb
