import typing
import os
from itertools import islice
import json
from datetime import datetime, timedelta

import openai
from nostr_dvm.utils.openai_utils import fetch_classification_response
from types import SimpleNamespace

from nostr_sdk import Alphabet,\
                    Event,\
                    Options,\
                    PublicKey,\
                    RelayFilteringMode,\
                    RelayLimits,\
                    Timestamp,\
                    Tag,\
                    SingleLetterTag,\
                    Keys,\
                    SecretKey,\
                    NostrSigner,\
                    Client,\
                    ClientBuilder,\
                    Filter,\
                    init_logger,\
                    LogLevel,\
                    Kind

from nostr_dvm.interfaces.dvmtaskinterface import DVMTaskInterface
from nostr_dvm.utils import definitions
from nostr_dvm.utils.admin_utils import AdminConfig
from nostr_dvm.utils.clean_events import clean_text
from nostr_dvm.utils.database_utils import init_db
from nostr_dvm.utils.definitions import EventDefinitions
from nostr_dvm.utils.dvmconfig import DVMConfig
from nostr_dvm.utils.nip88_utils import NIP88Config
from nostr_dvm.utils.nip89_utils import NIP89Config
from nostr_dvm.utils.output_utils import post_process_list_to_events
from nostr_dvm.utils.wot_utils import build_wot_network

"""
Discover nostr events relevant to freelancing: Git issues 
and kind1 notes filtered for people seeking help
Accepted Inputs: NONE (but later it could be personalized with interests of users)
Outputs: A list of events: Kind 1, Kind 1621(Git issues)
Params:  None
"""


class MuseDVM(DVMTaskInterface):
    KIND: Kind = EventDefinitions.KIND_NIP90_CONTENT_DISCOVERY
    TASK: str = "discover-content"
    FIX_COST: float = 0
    openai_client: openai.AsyncOpenAI
    wot_file_path: str
    wot_keys:typing.List[PublicKey] = []
    posts_file_path: str
    dvm_config: DVMConfig
    request_form = None
    last_schedule: int = 0
    db_since:int
    fetch_notes_since: Timestamp
    db_name: str
    result = ""

    def __init__(
        self,
        name,
        openai_client: openai.AsyncOpenAI,
        dvm_config: DVMConfig,
        nip89config: NIP89Config,
        nip88config: NIP88Config|None = None,
        admin_config: AdminConfig|None = None,
        options=None,
        task=None
    ):
        self.name = name
        self.NAME = name
        self.openai_client = openai_client
        self.dvm_config = dvm_config
        self.dvm_config.NIP89 = nip89config
        self.dvm_config.NIP88 = nip88config
        self.dvm_config.SUPPORTED_DVMS = [self]
        self.admin_config = admin_config

        wot_file_path = os.getenv("WOT_FILE_PATH")

        if wot_file_path is None:
            raise EnvironmentError("Could not load WOT file path!")

        self.wot_file_path = wot_file_path

        posts_file_path = os.getenv("PROCESSED_POSTS_PATH")

        if posts_file_path is None:
            raise EnvironmentError("Could not load PROCESSED_POSTS_PATH path!")

        self.posts_file_path = posts_file_path


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
            "max_results": max_results
        }

        self.request_form['options'] = json.dumps(opts)

        self.db_name = self.options.get("db_name")

        if self.db_name is None:
            raise ValueError("option 'db_name' \
            is None or the key does not exist. Add valid option!") 

        self.db_since = self.options.get("db_since")
        if self.db_since is None:
            raise ValueError("option 'db_since' \
            is None or the key does not exist. Add valid option!") 

        self.fetch_notes_since = Timestamp.from_secs(
            Timestamp.now().as_secs() - self.db_since
        )

        self.max_db_size = self.options.get("max_db_size")

        if self.max_db_size is None:
            raise ValueError(
                "'max_db_size' \
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
        self.database = await init_db(
            self.db_name,
            True,
            self.max_db_size
        )

        self.dvm_config.DB = self.db_name + '/users.db'

        print(f"Init db DONE{self.database.metadata}")

        # Query db for all kind1 notes and set fetch_notes_since to latest created_at
        # if there are posts in the DB. This handles state reload on dvm restarts and 
        # avoids unnecessary fetching and inference work on posts that are already processed.
        events_filter = Filter().kind(
            definitions.EventDefinitions.KIND_NOTE,
        )
        events_struct = await self.database.query([events_filter])
        for event in events_struct.to_vec():
            event_timestamp = event.created_at().as_secs()
            if event_timestamp > self.fetch_notes_since.as_secs():
                self.fetch_notes_since = Timestamp.from_secs(event_timestamp)

        print(f"Latest timestamp of already processed notes:\
            \n{self.fetch_notes_since.to_human_datetime()}"
        )

        init_logger(dvm_config.LOGLEVEL)


    async def is_input_supported(
            self,
            tags,
            client=None,
            dvm_config=None
    ):
        for tag in tags:
            if tag.as_vec()[0] == 'i':
                input_value = tag.as_vec()[1]
                input_type = tag.as_vec()[2]
                if input_type != "text":
                    return False
        return True

    async def create_request_from_nostr_event(
        self,
        event,
        client=None,
        dvm_config=None
    ):
        request_form = {"jobID": event.id().to_hex()}
        max_results = int(self.options.get("max_results"))

        for tag in event.tags().to_vec():
            if tag.as_vec()[0] == 'i':
                input_type = tag.as_vec()[2]
            elif tag.as_vec()[0] == 'param':
                param = tag.as_vec()[1]
                if param == "max_results":  # check for param type
                    max_results = int(tag.as_vec()[2])

        options = {
            "max_results": max_results,
            "request_event_id": event.id().to_hex(),
            "request_event_author": event.author().to_hex()
        }
        request_form['options'] = json.dumps(options)
        self.request_form = request_form
        return request_form


    async def process(self, request_form):
        print("Processing request, returning current result...")

        return self.result


    async def calculate_result(self, request_form):
        ns = SimpleNamespace()

        options = self.set_options(request_form)

        print(f"request_form: {request_form}")

        timestamp_since = Timestamp.now().as_secs() - self.db_since

        git_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE,
            ]
        )

        all_git_issue_events = await self.database.query([git_filter])

        if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
            print(
                "[" + self.dvm_config.NIP89.NAME + "] Considering "\
                + str(len(all_git_issue_events.to_vec())) + " Git issue events"
            )

        issue_status_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE_OPEN,
                definitions.EventDefinitions.KIND_GIT_ISSUE_RESOLVED,
                definitions.EventDefinitions.KIND_GIT_ISSUE_CLOSED,
                definitions.EventDefinitions.KIND_GIT_ISSUE_DRAFT
            ]
        )

        all_issue_statuses = await self.database.query([issue_status_filter])
        print(f"All issue statuses({len(all_issue_statuses.to_vec())}): {all_issue_statuses.to_vec()}")

        # tags().find(TagKind) does NOT work for now:
        # find(TagKind.SINGLE_LETTER(SingleLetterTag.lowercase(Alphabet('E')))))
        filtered_git_issue_events = []
        for git_issue in all_git_issue_events.to_vec():
            active_status = None
            latest_status_timestamp = 0
            for issue_status in all_issue_statuses.to_vec():

                for tag in issue_status.tags().to_vec():
                    tag_vec = tag.as_vec()
                    # print(f"Comparing {tag_vec[1]} ?= {git_issue.id().to_hex()}")

                    if tag_vec[0] == "e"\
                        and tag_vec[1] == git_issue.id().to_hex()\
                        and issue_status.created_at().as_secs() > latest_status_timestamp:
                        print(f"Found latest status of git issue: {issue_status.kind()}")
                        latest_status_timestamp = issue_status.created_at().as_secs()
                        active_status = Event.from_json(issue_status.as_json())

            if active_status is not None:
                print(f"Active status of git issue: {active_status.kind()}")

                if active_status.kind() == definitions.EventDefinitions.KIND_GIT_ISSUE_OPEN:
                    filtered_git_issue_events.append(Event.from_json(git_issue.as_json()))

            elif active_status is None:
                print(f"Could not find active status of issue: {git_issue}")

        print(f"Found {len(filtered_git_issue_events)} OPEN git issues")
        

        ns.git_events_list = {}

        for event in filtered_git_issue_events:
            ns.git_events_list[event.id().to_hex()] = event.created_at().as_secs()

        git_events_list_sorted = sorted(
            ns.git_events_list.items(),
            key=lambda x: x[1],
            reverse=True
        )

        all_processed_kind1s = self.load_processed_kind1s_from_file(timestamp_since)

        # Prepend kind1s in the front and take as many of them as the options allow
        result_list = []

        for event_id in all_processed_kind1s:
            e_tag = Tag.parse(["e", event_id])
            result_list.append(e_tag.as_vec())

        for entry in git_events_list_sorted:
            e_tag = Tag.parse(["e", entry[0]])
            result_list.append(e_tag.as_vec())

        result_list = result_list[:int(options["max_results"])]

        print(f"Result list({len(result_list)}):\n{result_list}")

        if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
            print("[" + self.dvm_config.NIP89.NAME + "] Filtered " + str(
                len(result_list)) + " fitting events.")

        return json.dumps(result_list)


    def load_processed_kind1s_from_file(self, timestamp_since) -> typing.List[str] :
        all_processed_kind1s = []
        # Add already processed posts to result which 
        with open(self.posts_file_path, 'a') as file:
            pass 

        with open(self.posts_file_path, 'r') as file:
            lines = file.readlines()
        for line in lines:
            # print(f"Reading line from saved processed notes file:\n{line}\n")
            parsed_line = line.split(":", 1)

            if len(parsed_line) != 2:
                continue

            post_id = parsed_line[0]
            created_at = parsed_line[1]
            try:
                if int(created_at.strip()) >= timestamp_since:
                    all_processed_kind1s.append(post_id.strip())
                else:
                    print(f"{created_at} not greater than {timestamp_since}, skip this event...\n")
            except ValueError:
                print(f"Could not convert event timestamp to int: {post_id}:{created_at}")
                continue

        # print(f"All kind1s parsed from file:\n{all_processed_kind1s}")
        return all_processed_kind1s


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
        # print("Schedule")
        if dvm_config.SCHEDULE_UPDATES_SECONDS == 0:
            raise ValueError("Error Schedule update period not set!")
        else:
            # initially last_schedule is 0 so this will be true
            if Timestamp.now().as_secs() >= self.last_schedule\
                        + dvm_config.SCHEDULE_UPDATES_SECONDS:
                print("Start schedule")

                if self.dvm_config.UPDATE_DATABASE:
                    await self.sync_db()

                self.last_schedule = Timestamp.now().as_secs()

                print("Calculating result...")
                self.result = await self.calculate_result(self.request_form)
                # print(f"Result:{self.result}")

                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                result_event = await self.process(self.request_form)

                try:
                    with open("test_results/test_result_muse_" + timestamp \
                    + '.txt', 'w', encoding="utf8") as output_file:

                        output_file.write(result_event)

                        print(f"Result written to {output_file.name}")

                except Exception as e:
                        print("Error: " + str(e))

                return 1
            else:
                return 0

    async def sync_db(self):
        if self.database is None:
            raise ValueError("Database cannot be None when\
                trying to sync up!"
            )

        try:
            print("Start Syncing DB...")

            cli = await self.build_nostr_client()

            await self.load_wot(cli)

            # Copy timestamp and set new anchor date for next fetch
            notes_since = Timestamp.from_secs(self.fetch_notes_since.as_secs())
            self.fetch_notes_since = Timestamp.now()
            time_span_notes = self.fetch_notes_since.as_secs() - notes_since.as_secs()

            print(f"Fetching notes since: {notes_since.to_human_datetime()}")

            await self.fetch_muse_events(cli, notes_since)

            print("Syncing complete, shutting down client...")

            await cli.shutdown()

            # Run inference on synced Kind1 events and save relevant ones in text file
            await self.filter_and_save_kind1_notes(notes_since)


            if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
                print("[" + self.dvm_config.NIP89.NAME
                        + "] Done Syncing Notes of the last "
                        + str(time_span_notes) + " seconds.."
                )

        except Exception as e:
            print(e)

    async def build_nostr_client(self) -> Client :
        relaylimits = RelayLimits.disable()
        opts = (Options().relay_limits(relaylimits))
        if self.dvm_config.WOT_FILTERING:
            opts = opts.filtering_mode(RelayFilteringMode.WHITELIST)
             
        # opts.gossip(True)

        sk = SecretKey.from_hex(self.dvm_config.PRIVATE_KEY)
        keys = Keys.parse(sk.to_hex())

        cli = ClientBuilder().signer(NostrSigner.keys(keys))\
                            .database(self.database)\
                            .opts(opts)\
                            .build()


        # Add discovery relays for gossip
        for relay in self.dvm_config.SYNC_DB_RELAY_LIST:
            await cli.add_relay(relay)
            # await cli.add_discovery_relay(relay)

        await cli.connect()
        print("Client connected.")

        return cli


    async def load_wot(self, cli):
            self.wot_keys.clear()

            #whitelisting Five (source of web of trust)
            self.wot_keys.append(PublicKey.parse(
                "d04ecf33a303a59852fdb681ed8b412201ba85d8d2199aec73cb62681d62aa90"
            ))
            self.wot_keys.append(PublicKey.parse(
                "3f770d65d3a764a9c5cb503ae123e62ec7598ad035d836e2a810f3877a745b24"
            ))
            self.wot_keys.append(PublicKey.parse(
                "460c25e682fda7832b52d1f22d3d22b3176d972f60dcdc3212ed8c92ef85065c"
            ))
            self.wot_keys.append(PublicKey.parse(
                "99bb5591c9116600f845107d31f9b59e2f7c7e09a1ff802e84f1d43da557ca64"
            ))

            if self.wot_outdated():
                print("Updating Web of Trust...")
                self.wot_keys = await self.update_wot()
                print(
                    f"""public keys just calculated:
                    \n{self.wot_keys[:10]}...({len(self.wot_keys)})"""
                )
            else:
                # MUST exist
                with open(self.wot_file_path, 'r') as wot_file:
                    lines = wot_file.readlines()
                    for line in lines:
                        pubkey_hex = line.strip()
                        try:
                            self.wot_keys.append(PublicKey.parse(pubkey_hex))
                        except Exception as e:
                            print(e)
                            continue

                print(
                    f"""public keys read from file:
                    \n{self.wot_keys[:10]}...({len(self.wot_keys)})"""
                )


            await cli.filtering().add_public_keys(self.wot_keys)

            print(f'WoT filter size:{len(self.wot_keys)}')


    def wot_outdated(self) -> bool:
        # Update wot every 2 days
        elapsed_time = timedelta(days=2)

        if not os.path.exists(self.wot_file_path):
            print("WOT file does not exist, no wot yet")
            return True

        mod_time = os.path.getmtime(self.wot_file_path)
        last_mod_date = datetime.fromtimestamp(mod_time)

        current_time = datetime.now()
        time_difference = current_time - last_mod_date

        print(f"File last modified: {last_mod_date}")
        print(f"Time elapsed since last modification: {time_difference}")

        if time_difference > elapsed_time:
            return True
        else:
            return False


    async def update_wot(self) -> typing.List[PublicKey]:
        try:
            print(
                "Calculating WOT for " \
                + str(self.dvm_config.WOT_BASED_ON_NPUBS)
            )

            index_map, G = await build_wot_network(
                self.dvm_config.WOT_BASED_ON_NPUBS,
                depth=self.dvm_config.WOT_DEPTH,
                max_batch=500,
                max_time_request=10,
                dvm_config=self.dvm_config
            )

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

            with open(self.wot_file_path, 'w') as wot_file: 
                for index, key in enumerate(wot_keys, start=0):
                    wot_file.write(key.to_hex())
                    if index < len(wot_keys) - 1:
                        wot_file.write('\n')

            return wot_keys
        except Exception as e:
            print(e)
            return []

    async def filter_and_save_kind1_notes(self, since):
        kind1_filter = Filter().kind(
            definitions.EventDefinitions.KIND_NOTE
        ).since(since)

        events = await self.database.query([kind1_filter])

        kind1_events = events.to_vec()

        # 4o-mini can handle 128K tokens per api request. Should handle
        # 500 posts easily including system message and output tokens
        # but we will keep it *100* for now, as it delivers better results

        # Posts are truncated to a max of 300 chars for safety in clean_text
        batch_size = 100
        print(f"Start kind1 processing with batch size: {batch_size}")
        all_processed_kind1s = []
        for i in range(0, len(kind1_events), batch_size):
            batch = kind1_events[i:i+batch_size]

            preprocessed_kind1s = ""
            for index, event in enumerate(batch):
                cleaned_content = clean_text(event.content())
                if cleaned_content == "":
                    continue

                preprocessed_kind1s += \
                    f"""{event.id().to_hex()[:4]}:{cleaned_content}"""
                if index < len(batch) - 1:
                    preprocessed_kind1s += ';;;;'
                        
            print(f"Sending {len(batch)} cleaned posts for inference")
            print(f"User prompt sample:\n{preprocessed_kind1s[:1000]}\n")

            start_time = datetime.now()
            processed_kind1s = await fetch_classification_response(
                self.openai_client, preprocessed_kind1s
            )

            # print(f"Processed events! Result:{processed_kind1s}")
            time_difference =  datetime.now() - start_time
            print(f"Processing events took {time_difference.seconds}secs")

            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

            wrote_first_event = False
            for index, line in enumerate(processed_kind1s):
                # There can be malformed output from inference, skip those
                response_info = line.split(":", 1)
                if len(response_info) != 2:
                    continue

                post_id = response_info[0]
                category = response_info[1]

                if '1' in category:
                    for event in batch:
                        if post_id == event.id().to_hex()[:4]: 
                            with open(self.posts_file_path, 'a') as file:
                                if not wrote_first_event:
                                    file.write("\n")
                                    wrote_first_event = True

                                file.write(
                                    f"""{event.id().to_hex()}:{event.created_at().as_secs()}"""
                                )

                                if index < len(processed_kind1s) - 1:
                                    file.write("\n")

                            with open('test_results/test_kind1_result_content_'\
                                + timestamp + '.txt', 'a'
                            ) as content_file:
                                content_file.write(
                                    f"""{event.id().to_hex()}:{event.content()}"""
                                )

                                if index < len(processed_kind1s) - 1:
                                    content_file.write("\n")

                            all_processed_kind1s.append(event)


        print(f'The overall result of the kind1 filtering\
            selected these events({len(all_processed_kind1s)}):\
            {all_processed_kind1s}'
        )


    async def fetch_muse_events(self, cli:Client, notes_since):
        # Have to add relays explicitly defined in Announced Git repos
        # in order to get the relevant issues and their replies
        git_repo_filter = Filter().kind(
            definitions.EventDefinitions.KIND_GIT_REPOSITORY
        )

        repo_events_struct = await cli.fetch_events(
            [git_repo_filter], timedelta(3)
        )
        repo_events: typing.List[Event] = repo_events_struct.to_vec()

        print(f"Repo events fetched: {len(repo_events)}pcs")

        repo_event_coords = []

        relay_urls_to_add = []
        for event in repo_events:
            # Have to construct this until coord() does not work
            kind_str = str(event.kind().as_u16())
            pubkey_str = event.author().to_hex()
            d_tag_str = None
            tags = event.tags()
            for tag in tags.to_vec():
                if tag.as_vec()[0] == 'd':
                    d_tag_str = tag.as_vec()[1]

            if d_tag_str is not None:
                repo_event_coords.append(f"{kind_str}:{pubkey_str}:{d_tag_str}")

            for tag in event.tags().to_vec():
                tag_array = tag.as_vec()
                if tag_array[0] == "relays":
                    relay_urls_to_add = tag_array[1:]
                    break

        print(f"Adding event coordinates from repo events: {repo_event_coords}")
        print(f"Adding relays from repo events: {relay_urls_to_add}")
        for url in relay_urls_to_add:
            await cli.add_relay(url)

        await cli.connect()

        relays = await cli.relays()
        print(f"Connected relays: {relays}")

        notes_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_NOTE,
            ]
        ).since(notes_since)

        issues_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE,
                # definitions.EventDefinitions.KIND_GIT_ISSUE_REPLY,
            ]
        ).custom_tag(
            SingleLetterTag.lowercase(Alphabet.A), repo_event_coords
        )

        issue_statuses_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE_OPEN,
                definitions.EventDefinitions.KIND_GIT_ISSUE_RESOLVED,
                definitions.EventDefinitions.KIND_GIT_ISSUE_CLOSED,
                definitions.EventDefinitions.KIND_GIT_ISSUE_DRAFT
            ]
        )

        open_issue_statuses_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE_OPEN,
            ]
        )
        open_issues = await cli.fetch_events([open_issue_statuses_filter],timedelta(5))
        print(f"fetched all open issue statuses: {len(open_issues.to_vec())} pcs")
        print(f"open issues: {open_issues.to_vec()}")

        start_time = datetime.now()

        note_events = await cli.fetch_events(
            [notes_filter],
            timedelta(10)
        )

        # remove wot for more results
        # await cli.filtering().remove_public_keys(self.wot_keys)

        issue_events = await cli.fetch_events(
            [issues_filter],
            timedelta(5)
        )

        issue_event_ids = []
        for issue_event in issue_events.to_vec():
            issue_event_ids.append(issue_event.id())

        issue_statuses_filter.events(issue_event_ids)

        issue_status_events = await cli.fetch_events(
            [issue_statuses_filter],
            timedelta(5)
        )

        time_difference =  datetime.now() - start_time
        relays = await cli.relays()
        print(f"Connected relays after fetch: {relays}")
        print(f"Fetching all events took {time_difference.seconds}secs")

        print(f"Number of notes fetched: {len(note_events.to_vec())}\n")
        print(f"Number of issues fetched: {len(issue_events.to_vec())}\n")
        print(f"Number of issue statuses fetched: {len(issue_status_events.to_vec())}\n")
        open_issues_counter = 0
        for issue_status in issue_status_events.to_vec():
            if issue_status.kind() == definitions.EventDefinitions.KIND_GIT_ISSUE_OPEN:
                open_issues_counter += 1


        print(f"{open_issues_counter} open issue status found")

async def build_muse(
    name,
    openai_client,
    dvm_config,
    nip89config,
    nip88config,
    admin_config,
    options,
):
    print(f"Options in build_muse:{options}")

    dvm = MuseDVM(
        name=name,
        openai_client = openai_client,
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



