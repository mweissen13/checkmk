#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# fmt: off
# type: ignore

checkname = 'msexch_isstore'

info = [[
    'Activemailboxes', 'AverageKeywordStatsSearchExecutionTime',
    'AverageKeywordStatsSearchExecutionTime_Base', 'AverageMultiMailboxSearchFailed',
    'AverageMultiMailboxSearchFailed_Base', 'AverageMultiMailboxSearchQueryLength',
    'AverageMultiMailboxSearchQueryLength_Base',
    'AverageMultiMailboxSearchtimespentinFullTextIndex',
    'AverageMultiMailboxSearchtimespentinFullTextIndex_Base',
    'AverageMultiMailboxSearchtimespentinStorecalls',
    'AverageMultiMailboxSearchtimespentinStorecalls_Base',
    'AveragenumberofKeywordsinMultiMailboxSearch',
    'AveragenumberofKeywordsinMultiMailboxSearch_Base', 'AverageSearchExecutionTime',
    'AverageSearchExecutionTime_Base', 'Averagesearchresultsperquery',
    'Averagesearchresultsperquery_Base', 'CachedeletesintheAddressInfocachePersec',
    'CachedeletesintheDatabaseInfocachePersec',
    'CachedeletesintheDistributionListMembershipcachePersec',
    'CachedeletesintheForeignAddressInfocachePersec',
    'CachedeletesintheForeignMailboxInfocachePersec',
    'CachedeletesintheIncompleteAddressInfocachePersec',
    'CachedeletesintheLogicalIndexcachePersec', 'CachedeletesintheMailboxInfocachePersec',
    'CachedeletesintheOrganizationContainercachePersec', 'CachehitsintheAddressInfocachePersec',
    'CachehitsintheDatabaseInfocachePersec',
    'CachehitsintheDistributionListMembershipcachePersec',
    'CachehitsintheForeignAddressInfocachePersec', 'CachehitsintheForeignMailboxInfocachePersec',
    'CachehitsintheIncompleteAddressInfocachePersec', 'CachehitsintheLogicalIndexcachePersec',
    'CachehitsintheMailboxInfocachePersec', 'CachehitsintheOrganizationContainercachePersec',
    'CacheinsertsintheAddressInfocachePersec', 'CacheinsertsintheDatabaseInfocachePersec',
    'CacheinsertsintheDistributionListMembershipcachePersec',
    'CacheinsertsintheForeignAddressInfocachePersec',
    'CacheinsertsintheForeignMailboxInfocachePersec',
    'CacheinsertsintheIncompleteAddressInfocachePersec',
    'CacheinsertsintheLogicalIndexcachePersec', 'CacheinsertsintheMailboxInfocachePersec',
    'CacheinsertsintheOrganizationContainercachePersec',
    'CachelookupsintheAddressInfocachePersec', 'CachelookupsintheDatabaseInfocachePersec',
    'CachelookupsintheDistributionListMembershipcachePersec',
    'CachelookupsintheForeignAddressInfocachePersec',
    'CachelookupsintheForeignMailboxInfocachePersec',
    'CachelookupsintheIncompleteAddressInfocachePersec',
    'CachelookupsintheLogicalIndexcachePersec', 'CachelookupsintheMailboxInfocachePersec',
    'CachelookupsintheOrganizationContainercachePersec', 'CachemissesintheAddressInfocachePersec',
    'CachemissesintheDatabaseInfocachePersec',
    'CachemissesintheDistributionListMembershipcachePersec',
    'CachemissesintheForeignAddressInfocachePersec',
    'CachemissesintheForeignMailboxInfocachePersec',
    'CachemissesintheIncompleteAddressInfocachePersec', 'CachemissesintheLogicalIndexcachePersec',
    'CachemissesintheMailboxInfocachePersec', 'CachemissesintheOrganizationContainercachePersec',
    'Caption', 'DatabaseLevelMaintenancesPersec', 'DatabaseState', 'Description',
    'FolderscreatedPersec', 'FoldersdeletedPersec', 'FoldersopenedPersec', 'Frequency_Object',
    'Frequency_PerfTime', 'Frequency_Sys100NS', 'IntegrityCheckDropBusyJobs',
    'IntegrityCheckFailedJobs', 'IntegrityCheckPendingJobs', 'IntegrityCheckTotalJobs',
    'LastMaintenanceItemRequestedAge', 'Lazyindexchunkedpopulations', 'LazyindexescreatedPersec',
    'LazyindexesdeletedPersec', 'LazyindexfullrefreshPersec',
    'LazyindexincrementalrefreshPersec', 'LazyindexinvalidationduetolocaleversionchangePersec',
    'LazyindexinvalidationPersec', 'Lazyindexnonchunkedpopulations',
    'Lazyindexpopulationsfromindex', 'Lazyindexpopulationswithouttransactionpulsing',
    'Lazyindextotalpopulations', 'LostDiagnosticEntries', 'MailboxesWithMaintenanceItems',
    'MailboxKeyDecryptAverageLatency', 'MailboxKeyDecryptAverageLatency_Base',
    'MailboxKeyDecryptsPersec', 'MailboxKeyEncryptsPersec', 'MailboxLevelMaintenanceItems',
    'MailboxLevelMaintenancesPersec', 'MAPIMessagesCreatedPersec', 'MAPIMessagesModifiedPersec',
    'MAPIMessagesOpenedPersec', 'MessagescreatedPersec', 'MessagesdeletedPersec',
    'MessagesDeliveredPersec', 'MessagesopenedPersec', 'MessagesSubmittedPersec',
    'MessagesupdatedPersec', 'MultiMailboxKeywordStatsSearchPersec',
    'MultiMailboxPreviewSearchPersec', 'MultiMailboxSearchFullTextIndexQueryPersec', 'Name',
    'NonrecursivefolderhierarchyreloadsPersec', 'Numberofactivebackgroundtasks',
    'NumberofactiveWLMLogicalIndexmaintenancetablemaintenances',
    'NumberofmailboxesmarkedforWLMLogicalIndexmaintenancetablemaintenance',
    'NumberofprocessingLogicalIndexmaintenancetasks',
    'NumberofscheduledLogicalIndexmaintenancetasks', 'PercentRPCRequests',
    'PercentRPCRequests_Base', 'ProcessID', 'PropertypromotionmessagesPersec',
    'PropertypromotionsPersec', 'PropertyPromotionTasks', 'QuarantinedComponentCount',
    'QuarantinedMailboxCount', 'QuarantinedSchemaUpgraderCount',
    'QuarantinedUserAccessibleMailboxCount', 'RecursivefolderhierarchyreloadsPersec',
    'RPCAverageLatency', 'RPCAverageLatency_Base', 'RPCOperationsPersec', 'RPCPacketsPersec',
    'RPCPoolContextHandles', 'RPCPoolParkedAsyncNotificationCalls', 'RPCPoolPools',
    'RPCRequests', 'ScheduledISIntegDetectedCount', 'ScheduledISIntegFixedCount',
    'ScheduledISIntegPersec', 'ScopeKeyReadAverageLatency', 'ScopeKeyReadAverageLatency_Base',
    'ScopeKeyReadsPersec', 'SearchPersec', 'SearchresultsPersec', 'SizeofAddressInfocache',
    'SizeofDatabaseInfocache', 'SizeofDistributionListMembershipcache',
    'SizeofForeignAddressInfocache', 'SizeofForeignMailboxInfocache',
    'SizeofIncompleteAddressInfocache', 'SizeofLogicalIndexcache', 'SizeofMailboxInfocache',
    'SizeofOrganizationContainercache', 'SizeoftheexpirationqueuefortheAddressInfocache',
    'SizeoftheexpirationqueuefortheDatabaseInfocache',
    'SizeoftheexpirationqueuefortheDistributionListMembershipcache',
    'SizeoftheexpirationqueuefortheForeignAddressInfocache',
    'SizeoftheexpirationqueuefortheForeignMailboxInfocache',
    'SizeoftheexpirationqueuefortheIncompleteAddressInfocache',
    'SizeoftheexpirationqueuefortheLogicalIndexcache',
    'SizeoftheexpirationqueuefortheMailboxInfocache',
    'SizeoftheexpirationqueuefortheOrganizationContainercache', 'SubobjectscleanedPersec',
    'SubobjectscreatedPersec', 'SubobjectsdeletedPersec', 'Subobjectsintombstone',
    'SubobjectsopenedPersec', 'SuccessfulsearchPersec', 'TimedEventsProcessed',
    'TimedEventsProcessedPersec', 'TimedEventsProcessingFailures', 'Timestamp_Object',
    'Timestamp_PerfTime', 'Timestamp_Sys100NS', 'TopMessagescleanedPersec',
    'Topmessagesintombstone', 'TotalfailedmultimailboxkeywordstatisticsSearches',
    'TotalfailedmultimailboxPreviewSearches', 'TotalMultiMailboxkeywordstatisticssearches',
    'Totalmultimailboxkeywordstatisticssearchestimedout', 'TotalMultiMailboxpreviewsearches',
    'Totalmultimailboxpreviewsearchestimedout',
    'TotalMultiMailboxsearchesfailedduetoFullTextfailure',
    'TotalmultimailboxsearchesFullTextIndexQueryExecution',
    'Totalnumberofsuccessfulsearchqueries', 'Totalobjectssizeintombstonebytes', 'Totalsearches',
    'Totalsearchesinprogress', 'Totalsearchqueriescompletedin005sec',
    'Totalsearchqueriescompletedin052sec', 'Totalsearchqueriescompletedin1060sec',
    'Totalsearchqueriescompletedin210sec', 'Totalsearchqueriescompletedin60sec'
],
        [
            '4', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0', '11705', '2038', '0', '0', '0', '0', '52', '7962', '0',
            '12671984', '18440396', '0', '0', '0', '0', '639930', '6127781', '0', '11708',
            '2038', '0', '0', '0', '0', '623', '7964', '0', '12684158', '18442669', '0',
            '12174', '8514', '0', '641176', '6136295', '0', '12174', '2273', '0', '12174',
            '8514', '0', '1246', '8514', '0', '', '11724', '1', '', '0', '0', '1220570',
            '0', '1953125', '10000000', '0', '0', '0', '0', '0', '0', '3', '24', '3',
            '838', '0', '0', '0', '2', '0', '3', '0', '1', '0', '0', '0', '0', '1',
            '11680', '40243', '51785', '66714', '80486', '23006', '28741', '101226',
            '11502', '23140', '0', '0', '0', 'db3', '0', '0', '0', '1', '0', '0', '0',
            '50', '5716', '0', '0', '0', '0', '0', '0', '0', '284', '1977204',
            '4308720', '6138327', '4308720', '23304', '8', '11650', '0', '0', '0', '0',
            '0', '0', '0', '0', '0', '3', '1', '0', '0', '0', '0', '8', '2', '0',
            '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0', '0', '0', '6743176366056', '130951777565810000', '23004', '2',
            '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0'
        ],
        [
            '4', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0', '11705', '2038', '0', '0', '0', '0', '52', '7962', '0',
            '12671984', '18440397', '0', '0', '0', '0', '639930', '6127781', '0', '11708',
            '2039', '0', '0', '0', '0', '623', '7964', '0', '12684158', '18442671', '0',
            '12174', '8514', '0', '641176', '6136295', '0', '12174', '2274', '0', '12174',
            '8514', '0', '1246', '8514', '0', '', '11724', '1', '', '0', '0', '1220570',
            '0', '1953125', '10000000', '0', '0', '0', '0', '0', '0', '3', '24', '3',
            '838', '0', '0', '0', '2', '0', '3', '0', '1', '0', '0', '0', '0', '1',
            '11680', '40243', '51785', '66714', '80486', '23006', '28741', '101226',
            '11502', '23140', '0', '0', '0', '_total', '0', '0', '0', '1', '0', '0',
            '0', '50', '5716', '0', '0', '0', '0', '0', '0', '0', '284', '1977204',
            '4308720', '6138327', '4308720', '23336', '9', '11651', '0', '0', '0', '0',
            '0', '0', '0', '0', '0', '3', '2', '0', '0', '0', '0', '8', '2', '0',
            '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0', '0', '0', '6743176366056', '130951777565810000', '23004', '2',
            '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0',
            '0', '0', '0'
        ]]

discovery = {'': [('_total', None), ('db3', None)]}

checks = {
    '': [
        ('_total', {
            'store_latency': {
                'upper': (40.0, 50.0)
            },
            'clienttype_requests': {
                'upper': (60, 70)
            },
            'clienttype_latency': {
                'upper': (40.0, 50.0)
            }
        }, [(0, 'Average latency: 0.46 ms', [('average_latency', 0.45888430902913163, 40.0, 50.0,
                                            None, None)])]),
        ('db3', {
            'store_latency': {
                'upper': (40.0, 50.0)
            },
            'clienttype_requests': {
                'upper': (60, 70)
            },
            'clienttype_latency': {
                'upper': (40.0, 50.0)
            }
        }, [(0, 'Average latency: 0.46 ms', [('average_latency', 0.45888430902913163, 40.0, 50.0,
                                            None, None)])]),
    ]
}
