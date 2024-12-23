import typing
import os
from pathlib import Path
from itertools import islice
import json
from datetime import datetime, timedelta

from nostr_sdk import Alphabet,\
                    Event,\
                    EventId,\
                    Options,\
                    PublicKey,\
                    RelayFilteringMode,\
                    RelayLimits,\
                    RelayOptions,\
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
Accepted Inputs: NONE (but later it could be personalized with interests of users)
Outputs: A list of events: Kind 1621(Git issues) with OPEN status
Params:  None
"""


class MuseGit(DVMTaskInterface):
    KIND: Kind = EventDefinitions.KIND_NIP90_CONTENT_DISCOVERY
    TASK: str = "discover-content"
    FIX_COST: float = 0
    wot_file_path: str
    last_issues_fetch_file_path: str
    wot_keys:typing.List[PublicKey] = []
    dvm_config: DVMConfig
    request_form = None
    last_schedule: int = 0
    db_since:int
    db_name: str
    result = ""

    def __init__(
        self,
        name,
        dvm_config: DVMConfig,
        nip89config: NIP89Config,
        nip88config: NIP88Config|None = None,
        admin_config: AdminConfig|None = None,
        options=None,
        task=None
    ):
        self.name = name
        self.NAME = name
        self.dvm_config = dvm_config
        self.dvm_config.NIP89 = nip89config
        self.dvm_config.NIP88 = nip88config
        self.dvm_config.SUPPORTED_DVMS = [self]
        self.admin_config = admin_config

        wot_file_path = os.getenv("WOT_FILE_PATH")

        if wot_file_path is None:
            raise EnvironmentError("Could not load 'WOT_FILE_PATH'!")

        self.wot_file_path = wot_file_path

        last_issues_fetch_file_path = os.getenv("LAST_ISSUES_FETCHED_FILE_PATH")

        if last_issues_fetch_file_path is None:
            raise EnvironmentError("Could not load 'LAST_ISSUES_FETCHED_FILE_PATH'!")

        self.last_issues_fetch_file_path = last_issues_fetch_file_path


        paths_to_create = [wot_file_path, last_issues_fetch_file_path]
        for path in paths_to_create:
            try:
                file_path = Path(path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error: Could not create directories for {path}. Reason: {e}")

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
        options = self.set_options(request_form)

        print(f"request_form: {request_form}")

        open_issue_events = self.load_open_issues()

        open_issues_list = []

        # How should the posts be arranged in the result?
        for event_id in open_issue_events:
            id:EventId = EventId.parse(event_id)
            relays_seen = await self.database.event_seen_on_relays(id)
            relay_hint = ''

            if relays_seen is not None:
                relay_hint = relays_seen[0]

            e_tag = Tag.parse(["e", event_id, relay_hint])
            open_issues_list.append(e_tag.as_vec())

        result_list = open_issues_list[:int(options["max_results"])]

        if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
            print("[" + self.dvm_config.NIP89.NAME + "] Filtered " + str(
                len(result_list)) + " fitting events.")

        return json.dumps(result_list)


    def load_open_issues(self) -> typing.List[str]:
        issue_ids = []
        with open(self.last_issues_fetch_file_path, 'a') as file:
            pass 

        with open(self.last_issues_fetch_file_path, 'r') as file:
            lines = file.readlines()
        for line in lines:
            try:
                post_id = line.strip()
                if line != '':
                    Tag.parse(['e', post_id])
                    issue_ids.append(post_id)

            except Exception as e:
                print(f"Error while parsing open issue: {e}\nContinuing..")
                continue

        return issue_ids


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

            await self.fetch_and_save_muse_git_events(cli)

            print("Syncing complete, shutting down client...")

            await cli.shutdown()

            if self.dvm_config.LOGLEVEL.value >= LogLevel.DEBUG.value:
                print("[" + self.dvm_config.NIP89.NAME
                        + "] Done Syncing Git issues"
                )

        except Exception as e:
            print(e)

    async def build_nostr_client(self) -> Client :
        relaylimits = RelayLimits.disable()
        opts = Options().relay_limits(relaylimits)\
                        .automatic_authentication(False)
        if self.dvm_config.WOT_FILTERING:
            opts = opts.filtering_mode(RelayFilteringMode.WHITELIST)
             
        # opts = opts.gossip(True)

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


    async def fetch_and_save_muse_git_events(self, cli:Client):
        start_time = datetime.now()

        # Fetch this less often, takes about 4mins
        if self.issues_outdated():
            await self.fetch_and_save_open_issues(cli)
            time_difference =  datetime.now() - start_time
            print(f"Fetching all events took {time_difference.seconds}secs")
        else:
            print("Git issues not yet outdated, no need to fetch!")

        # relays = await cli.relays()
        # print(f"Connected relays after fetch: {relays}")

    
    async def fetch_and_save_open_issues(self, cli):
        repo_events = await self.fetch_repos(cli)

        overall_issue_status_events:typing.List[Event] = []
        overall_issue_events:typing.List[Event] = []

        # Have to add relays explicitly defined in Announced Git repos
        # in order to get the relevant issues and their replies

        # custom relay opts and timeout settings to not get rekt while trying 
        # too many relays. timedelta(seconds = ...)
        relay_opts = RelayOptions().reconnect(False).ping(False)

        batch = 5
        print(f"Start fetching all git repos and their issues and issue statuses\
            with batch size: {batch}"
        )
        for i in range(0, len(repo_events), batch):
            try:
                print(f"FETCH ISSUES AND STATUSES OF REPOS: {i} : {i+batch}")
                batched_repo_events = repo_events[i:i+batch]
                repo_event_coords = []
                repo_urls = []

                self.extract_a_tags_and_relays_from_repo_events(
                    batched_repo_events,
                    repo_event_coords,
                    repo_urls
                )

                print(f"Adding event coordinates from repo events: {repo_event_coords}")

                await self.add_parsed_repo_relays(cli, repo_urls, relay_opts)

                issue_events_of_repo = await self.fetch_issues(cli, repo_event_coords)

                overall_issue_events += issue_events_of_repo


                issue_status_events_of_repo = await self.fetch_issue_statuses(
                    cli,
                    issue_events_of_repo
                )

                overall_issue_status_events += issue_status_events_of_repo

                print(f"Removing relays from repo events: {repo_urls}")
                for url in repo_urls:
                    try:
                        # await cli.pool().remove_relay(url)
                        await cli.remove_relay(url)
                    except Exception as e:
                        print(f"Exception while removing relay: {e}")
                        continue
                print(f"fetched {i+batch} repos and their issues and statuses!")
            except Exception as e:
                print(f"Exception happened while fetching git stuff: {e}\nContinuing...")
                continue


        print(f"Number of issues fetched: {len(overall_issue_events)}\n")

        print(f"Number of issue statuses fetched:\
            {len(overall_issue_status_events)}\n"
        )

        open_issues = self.find_open_issues(
            overall_issue_events,
            overall_issue_status_events
        )
        print(f"{len(open_issues)} issues found overall, writing to file...")
        with open(self.last_issues_fetch_file_path, 'w') as file:
            for git_issue in open_issues:
                file.write(git_issue.id().to_hex() + '\n')


    async def fetch_repos(self, cli) -> typing.List[Event]:
        # test = 'ngit'
        git_repo_filter = Filter().kind(
            definitions.EventDefinitions.KIND_GIT_REPOSITORY
        )#.custom_tag(
        #     SingleLetterTag.lowercase(Alphabet.D), [test]
        # )

        repo_events_struct = await cli.fetch_events(
            [git_repo_filter], timedelta(seconds = 5)
        )
        repo_events: typing.List[Event] = repo_events_struct.to_vec()

        print(f"Repo events fetched: {len(repo_events)}pcs")
        return repo_events


    def extract_a_tags_and_relays_from_repo_events(
        self,
        repo_events,
        repo_event_coords,
        repo_urls
    ):
        for repo_event in repo_events:
            # Have to construct event coordinate while coord() does not work
            kind_str = str(repo_event.kind().as_u16())
            pubkey_str = repo_event.author().to_hex()
            d_tag_str = None
            tags = repo_event.tags()
            for tag in tags.to_vec():
                if tag.as_vec()[0] == 'd':
                    d_tag_str = tag.as_vec()[1]

            if d_tag_str is not None:
                repo_event_coords.append(f"{kind_str}:{pubkey_str}:{d_tag_str}")

            for tag in repo_event.tags().to_vec():
                tag_array = tag.as_vec()
                if tag_array[0] == "relays":
                    repo_urls += tag_array[1:]
                    break

    async def add_parsed_repo_relays(self, cli, repo_urls, relay_opts):
        print(f"Adding relays from repo events: {repo_urls}")
        for url in repo_urls:
            try:
                # add relays with custom opts to pool
                await cli.pool().add_relay(url, relay_opts)
            except Exception as e:
                print(f"Exception while adding relay: {e}")
                continue

        await cli.connect_with_timeout(timedelta(seconds = 20))

        relays = await cli.relays()
        print(f"Connected relays: {relays}")

    async def fetch_issues(self, cli, repo_event_coords) -> typing.List[Event]:
        issues_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE,
                # definitions.EventDefinitions.KIND_GIT_ISSUE_REPLY,
            ]
        ).custom_tag(
            SingleLetterTag.lowercase(Alphabet.A), repo_event_coords
        )

        print("Fetching issues from repos...")
        issue_events_struct = await cli.fetch_events(
            [issues_filter],
            timedelta(seconds = 15)
        )
        print(f"Fetched all issues from repos:\
            {len(issue_events_struct.to_vec())}"
        )

        return issue_events_struct.to_vec()


    async def fetch_issue_statuses(
        self,
        cli,
        issue_events_of_repo
    ) -> typing.List[Event]:
        issue_statuses_filter = Filter().kinds(
            [
                definitions.EventDefinitions.KIND_GIT_ISSUE_OPEN,
                definitions.EventDefinitions.KIND_GIT_ISSUE_RESOLVED,
                definitions.EventDefinitions.KIND_GIT_ISSUE_CLOSED,
                definitions.EventDefinitions.KIND_GIT_ISSUE_DRAFT
            ]
        )

        issue_event_ids = []
        for issue_event in issue_events_of_repo:
            issue_event_ids.append(issue_event.id())

        issue_statuses_filter = issue_statuses_filter.events(
            issue_event_ids
        )

        print("Fetching statuses of issues from repos...")

        issue_status_events_struct = await cli.fetch_events(
            [issue_statuses_filter],
            timedelta(seconds = 15)
        )

        issue_status_events_of_repo = issue_status_events_struct.to_vec()

        print(f"Fetched all statuses of issues from repos:\
            {len(issue_status_events_of_repo)}"
        )

        return issue_status_events_of_repo


    def issues_outdated(self) -> bool:
        # Update wot every 2 days
        elapsed_time = timedelta(days=2)

        if not os.path.exists(self.last_issues_fetch_file_path):
            print("Last issues fetched file does not exist, no fetch yet")
            return True

        mod_time = os.path.getmtime(self.last_issues_fetch_file_path)
        last_mod_date = datetime.fromtimestamp(mod_time)

        current_time = datetime.now()
        time_difference = current_time - last_mod_date

        print(f"File last modified: {last_mod_date}")
        print(f"Time elapsed since last modification: {time_difference}")

        if time_difference > elapsed_time:
            return True
        else:
            return False


    def find_open_issues(
        self,
        all_git_issue_events: typing.List[Event], 
        all_issue_statuses: typing.List[Event]
    ) -> typing.List[Event]:
        # tags().find(TagKind) does NOT work for now:
        # find(TagKind.SINGLE_LETTER(SingleLetterTag.lowercase(Alphabet('E')))))
        filtered_git_issue_events:typing.List[Event] = []
        for git_issue in all_git_issue_events:
            active_status = None
            latest_status_timestamp = 0
            status_counter = 0
            for issue_status in all_issue_statuses:

                for tag in issue_status.tags().to_vec():
                    tag_vec = tag.as_vec()
                    # print(f"ISSUE's tags:\n{tag_vec}")
                    # print(f"Comparing {tag_vec[1]} ?= {git_issue.id().to_hex()}")
                    if tag_vec[0] == "e"\
                        and tag_vec[1] == git_issue.id().to_hex()\
                        and issue_status.created_at().as_secs() > latest_status_timestamp:
                        print(f"Found latest status of git issue: {issue_status.kind()}")
                        latest_status_timestamp = issue_status.created_at().as_secs()
                        active_status = Event.from_json(issue_status.as_json())
                        status_counter += 1

            print(f"{status_counter} statuses found for issue")

            if active_status is not None:
                print(f"Active status of git issue: {active_status.kind()}")

                if active_status.kind() == definitions.EventDefinitions\
                                            .KIND_GIT_ISSUE_OPEN:
                    filtered_git_issue_events.append(git_issue)


            elif active_status is None:
                print(f"Could not find active status of issue: \
                    {git_issue}\nDefaulting to OPEN"
                )
                filtered_git_issue_events.append(git_issue)
            else:
                print(f"Issue is NOT open! Status: {active_status}")

        print(f"Found {len(filtered_git_issue_events)} OPEN git issues")

        filtered_git_issue_events.sort(
            key=lambda event: event.created_at().as_secs(),
            reverse=True
        )

        return filtered_git_issue_events


async def build_muse_git(
    name,
    dvm_config,
    nip89config,
    nip88config,
    admin_config,
    options,
):
    print(f"Options in build_muse:{options}")

    dvm = MuseGit(
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



