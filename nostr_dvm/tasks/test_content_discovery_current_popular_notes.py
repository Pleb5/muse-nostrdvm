from itertools import islice
import json
from datetime import datetime

from nostr_sdk import Options, PublicKey, RelayFilteringMode, RelayLimits, Timestamp, Tag, Keys, SecretKey, NostrSigner, NostrDatabase, \
    ClientBuilder, Filter, SyncOptions, SyncDirection, init_logger, LogLevel, Kind

from nostr_dvm.interfaces.dvmtaskinterface import DVMTaskInterface
from nostr_dvm.utils import definitions
from nostr_dvm.utils.admin_utils import AdminConfig
from nostr_dvm.utils.database_utils import init_db
from nostr_dvm.utils.definitions import EventDefinitions
from nostr_dvm.utils.dvmconfig import DVMConfig
from nostr_dvm.utils.nip88_utils import NIP88Config
from nostr_dvm.utils.nip89_utils import NIP89Config
from nostr_dvm.utils.output_utils import post_process_list_to_events
from nostr_dvm.utils.wot_utils import build_wot_network

"""
This File contains a Module to discover popular notes
Accepted Inputs: none
Outputs: A list of events 
Params:  None
"""


class TestDicoverContentCurrentlyPopular(DVMTaskInterface):
    KIND: Kind = EventDefinitions.KIND_NIP90_CONTENT_DISCOVERY
    TASK: str = "discover-content"
    FIX_COST: float = 0
    dvm_config: DVMConfig
    request_form = None
    last_schedule: int = 0
    db_since = 3600
    db_name = "db/nostr_recent_notes.db"
    min_reactions = 5
    personalized = False
    result = ""

    # This has to be defined to avoid the super class 
    # __init__ to be invoked implicitly (which calls asyncio operations unnecessarily)
    def __init__(
        self,
        name,
        dvm_config: DVMConfig,
        nip89config: NIP89Config,
        nip88config: NIP88Config = None,
        admin_config: AdminConfig = None,
        options=None,
        task=None
    ):
        self.name = name
        self.NAME = name
        self.dvm_config = dvm_config
        self.dvm_config.NIP89 = nip89config
        self.dvm_config.SUPPORTED_DVMS = [self]
        self.admin_config = admin_config
        self.wot_counter = 0

        print(f"Options:{options}")

        if options is None:
            raise ValueError("'options' param in 'init_dvm' MUST NOT be None!\
            Cannot init dvm")
    
        self.request_form = {"jobID": "generic"}

        self.options = options

        max_results = self.options.get("max_results")

        if max_results is None:
            raise ValueError("option 'max_results' \
            is None or the key does not exist. Add valid option!") 

        opts = {
            "max_results": int(self.options.get("max_results"))
        }

        self.request_form['options'] = json.dumps(opts)

        self.db_name = self.options.get("db_name")
        self.dvm_config.DB = self.db_name

        db_since = self.options.get("db_since")
        self.max_db_size = self.options.get("max_db_size")

        if self.db_name is None or db_since is None or self.max_db_size is None:
            raise ValueError(
                "'db_name' or 'db_since' or 'db_limit' \
                is None or the key does not exist. Add valid options!"
            ) 


    async def init_dvm(
        self,
        name,
        dvm_config: DVMConfig,
        nip89config: NIP89Config|None = None,
        nip88config: NIP88Config|None = None,
        admin_config: AdminConfig|None = None,
        options=None
    ):
        print("Init db")
        self.database = await init_db(self.db_name, True, self.max_db_size)
        print("Init db DONE")

        init_logger(dvm_config.LOGLEVEL)


    async def is_input_supported(self, tags, client=None, dvm_config=None):
        for tag in tags:
            if tag.as_vec()[0] == 'i':
                input_value = tag.as_vec()[1]
                input_type = tag.as_vec()[2]
                if input_type != "text":
                    return False
        return True

    async def create_request_from_nostr_event(self, event, client=None, dvm_config=None):
        self.dvm_config = dvm_config

        request_form = {"jobID": event.id().to_hex()}

        # default values
        search = ""
        max_results = 200

        for tag in event.tags().to_vec():
            if tag.as_vec()[0] == 'i':
                input_type = tag.as_vec()[2]
            elif tag.as_vec()[0] == 'param':
                param = tag.as_vec()[1]
                if param == "max_results":  # check for param type
                    max_results = int(tag.as_vec()[2])

        options = {
            "max_results": max_results,
        }
        request_form['options'] = json.dumps(options)
        return request_form

    async def process(self, request_form):
        print("Process")

        # if the dvm supports individual results, recalculate it every time for the request
        if self.personalized:
            return await self.calculate_result(request_form)
        # else return the result that gets updated once every schenduled update. In this case on database update.
        else:
            return self.result

    async def calculate_result(self, request_form):
        from nostr_sdk import Filter
        from types import SimpleNamespace
        ns = SimpleNamespace()

        options = self.set_options(request_form)
        database = NostrDatabase.lmdb(self.db_name)

        print(f"request_form: {request_form}")

        timestamp_since = Timestamp.now().as_secs() - self.db_since
        since = Timestamp.from_secs(timestamp_since)

        filter1 = Filter().kind(definitions.EventDefinitions.KIND_NOTE).since(since)

        events = await database.query([filter1])
        if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
            print("[" + self.dvm_config.NIP89.NAME + "] Considering " + str(len(events.to_vec())) + " Events")
        ns.finallist = {}
        for event in events.to_vec():
            if event.created_at().as_secs() > timestamp_since:
                filt = Filter().kinds(
                    [
                        definitions.EventDefinitions.KIND_ZAP,
                        definitions.EventDefinitions.KIND_REPOST,
                        definitions.EventDefinitions.KIND_REACTION,
                        definitions.EventDefinitions.KIND_NOTE
                    ]
                ).event(event.id()).since(since)

                reactions = await database.query([filt])

                if len(reactions.to_vec()) >= self.min_reactions:
                    ns.finallist[event.id().to_hex()] = len(reactions.to_vec())
        if len(ns.finallist) == 0:
            return self.result

        result_list = []
         
        finallist_sorted = sorted(
            ns.finallist.items(),
            key=lambda x: x[1],
            reverse=True
        )[:int(options["max_results"])]

        for entry in finallist_sorted:
            # print(EventId.parse(entry[0]).to_bech32() + "/" + EventId.parse(entry[0]).to_hex() + ": " + str(entry[1]))
            e_tag = Tag.parse(["e", entry[0]])
            result_list.append(e_tag.as_vec())
        if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
            print("[" + self.dvm_config.NIP89.NAME + "] Filtered " + str(
                len(result_list)) + " fitting events.")
        # await cli.shutdown()
        return json.dumps(result_list)

    async def post_process(self, result, event):
        """Overwrite the interface function to return a \
        social client readable format, if requested"""

        for tag in event.tags().to_vec():
            if tag.as_vec()[0] == 'output':
                format = tag.as_vec()[1]
                if format == "text/plain":  # check for output type
                    result = post_process_list_to_events(result)

        # if not text/plain, don't post-process
        return result

    async def schedule(self, dvm_config):
        print("Schedule")
        if dvm_config.SCHEDULE_UPDATES_SECONDS == 0:
            print("Update period not set, returning...")
            return 0
        else:
            print("Start schedule")
            # initially last_schedule is 0 so this will be true
            if Timestamp.now().as_secs() >= self.last_schedule + dvm_config.SCHEDULE_UPDATES_SECONDS:
                if self.dvm_config.UPDATE_DATABASE:
                    await self.sync_db()

                self.last_schedule = Timestamp.now().as_secs()

                print("Calculating result...")
                self.result = await self.calculate_result(self.request_form)
                print(f"Result:{self.result}")

                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                result_event = await self.process(self.request_form)

                try:
                    with open("test_result.txt_" + timestamp, 'w', encoding="utf8") as output_file:
                        output_file.write(result_event)
                        print(f"Result written to {output_file.name}")
                except Exception as e:
                        print("Error: " + str(e))

                return 1
            else:
                return 0

    async def sync_db(self):
        print("Sync db")
        if self.database is None:
            raise ValueError("Database cannot be None when trying to sync up!")

        try:
            print("Start Sync DB...")
            relaylimits = RelayLimits.disable()
            opts = (Options().relay_limits(relaylimits))
            if self.dvm_config.WOT_FILTERING:
                opts = opts.filtering_mode(RelayFilteringMode.WHITELIST)

            sk = SecretKey.from_hex(self.dvm_config.PRIVATE_KEY)
            keys = Keys.parse(sk.to_hex())

            database = NostrDatabase.lmdb(self.db_name)

            cli = ClientBuilder().signer(
                NostrSigner.keys(keys)
            ).database(database).build()

            for relay in self.dvm_config.SYNC_DB_RELAY_LIST:
                await cli.add_relay(relay)

            await cli.connect()
            print("Client connected.")

            print("WOT Filtering: " + str(self.dvm_config.WOT_FILTERING))

            if self.dvm_config.WOT_FILTERING and self.wot_counter == 0:
                print("Calculating WOT for " + str(self.dvm_config.WOT_BASED_ON_NPUBS))
                filtering = cli.filtering()

                index_map, G = await build_wot_network(
                    self.dvm_config.WOT_BASED_ON_NPUBS,
                    depth=self.dvm_config.WOT_DEPTH,
                    max_batch=500,
                    max_time_request=10,
                    dvm_config=self.dvm_config
                )

                # Do we actually need pagerank here?
                # print('computing global pagerank...')
                # tic = time.time()
                # p_G = nx.pagerank(G, tol=1e-12)
                # print("network after pagerank: " + str(len(p_G)))

                wot_keys = []
                for item in islice(G, len(G)):
                    key = next(
                        (
                            PublicKey.parse(pubkey) for pubkey,
                            id in index_map.items() if id == item
                        ),
                        None
                    )

                    wot_keys.append(key)

                # toc = time.time()
                # print(f'finished in {toc - tic} seconds')
                await filtering.add_public_keys(wot_keys)

            self.wot_counter += 1
            # only calculate wot every 50th call
            if self.wot_counter > 49:
                self.wot_counter = 0

            timestamp_since = Timestamp.now().as_secs() - self.db_since
            since = Timestamp.from_secs(timestamp_since)

            filter1 = Filter().kinds(
                [
                    definitions.EventDefinitions.KIND_NOTE,
                    definitions.EventDefinitions.KIND_REACTION,
                    definitions.EventDefinitions.KIND_ZAP
                ]).since(since)

            # filter = Filter().author(keys.public_key())
            if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
                print(
                    "[" + self.dvm_config.NIP89.NAME
                    + "] Syncing notes of the last " 
                    + str(self.db_since)
                    + " seconds.. this might take a while.."
                )

            dbopts = SyncOptions().direction(SyncDirection.DOWN)
            await cli.sync(filter1, dbopts)

            # Clear old events so db doesn't get too full.
            await cli.database().delete(Filter().until(Timestamp.from_secs(
                Timestamp.now().as_secs() - self.db_since))
            )  
            print("Syncing complete, shutting down client...")

            await cli.shutdown()

            if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
                print("[" + self.dvm_config.NIP89.NAME
                        + "] Done Syncing Notes of the last "
                        + str(self.db_since) + " seconds.."
                )

        except Exception as e:
            print(e)


async def build_test(
    name,
    dvm_config,
    nip89config,
    nip88config,
    admin_config,
    options,
):
    print(f"Options in build_test:{options}")

    dvm = TestDicoverContentCurrentlyPopular(
        name=name,
        dvm_config=dvm_config,
        nip89config=nip89config,
        nip88config=nip88config,
        admin_config=admin_config,
        options=options
    )

    await dvm.init_dvm(
        dvm.name,
        dvm.dvm_config,
        nip89config,
        None,
        dvm.admin_config,
        dvm.options
    )

    return dvm



