from datetime import datetime
import os
import asyncio
import json
from pathlib import Path
import dotenv

from nostr_dvm.interfaces.dvmtaskinterface import DVMTaskInterface, process_venv
from nostr_dvm.tasks.content_discovery_update_db_only import DicoverContentDBUpdateScheduler
from nostr_dvm.tasks.test_content_discovery_current_popular_notes import TestDicoverContentCurrentlyPopular, build_test
from nostr_dvm.utils.admin_utils import AdminConfig
from nostr_dvm.utils.definitions import EventDefinitions
from nostr_dvm.utils.dvmconfig import DVMConfig, build_default_config
from nostr_dvm.utils.nip89_utils import NIP89Config, check_and_set_d_tag, create_amount_tag
from nostr_sdk import Keys, Kind, LogLevel



async def configure_and_start_DVM():
    try:
        # ------------------- ADMIN CONFIG
        admin_config = AdminConfig()
        admin_config.PRIVKEY = os.getenv("ADMIN_PRIVATE_KEY")
        admin_config.REBROADCAST_NIP89 = True
        admin_config.REBROADCAST_NIP65_RELAY_LIST = True
        admin_config.UPDATE_PROFILE = True
        admin_config.LUD16 = 'five@npub.cash'

        # ------------------- DVM CONFIG
        dvm_config = DVMConfig()
        dvm_config.LOGLEVEL = LogLevel.DEBUG
        dvm_config.PRIVATE_KEY: str = os.getenv("DVM_PRIVATE_KEY")
        dvm_config.PUBLIC_KEY = Keys.parse(dvm_config.PRIVATE_KEY).public_key().to_hex()
        dvm_config.FIX_COST: float = 0
        dvm_config.PER_UNIT_COST: float = 0

        dvm_config.USE_OWN_VENV = False
        dvm_config.SCHEDULE_UPDATES_SECONDS = 120  # Every 10 minutes
        dvm_config.UPDATE_DATABASE = True
        dvm_config.CUSTOM_PROCESSING_MESSAGE = None
        dvm_config.LN_ADDRESS = admin_config.LUD16

        dvm_config.RELAY_LIST = [
                "wss://relay.primal.net",
                "wss://nostr.mom",
                "wss://nostr.oxtr.dev",
            ]

        dvm_config.SYNC_DB_RELAY_LIST = [
                "wss://relay.damus.io",
                "wss://nos.lol",
                "wss://nostr.oxtr.dev",
            ]

        dvm_config.WOT_FILTERING = True

        dvm_config.WOT_BASED_ON_NPUBS = [
                # Don'tBelieveTheHype
                # "99bb5591c9116600f845107d31f9b59e2f7c7e09a1ff802e84f1d43da557ca64",
                # Vitor Pamplona
                # "460c25e682fda7832b52d1f22d3d22b3176d972f60dcdc3212ed8c92ef85065c",
                # Derek Ross
                # "3f770d65d3a764a9c5cb503ae123e62ec7598ad035d836e2a810f3877a745b24",
                #Five
                "d04ecf33a303a59852fdb681ed8b412201ba85d8d2199aec73cb62681d62aa90"
            ]
        dvm_config.WOT_DEPTH = 2

        dvm_config.RELAY_TIMEOUT = 5
        dvm_config.RELAY_LONG_TIMEOUT = 30

        dvm_config.CUSTOM_PROCESSING_MESSAGE = "TEST Processing request..."


        # ------------------- NIP89 CONFIG
        name = "Five Test Content Discovery DVM"
        image = "https://i.nostr.build/yq7a5.jpg"
        identifier = "five_test_content_discovery" 
        cost = 0

        # Add NIP89
        nip89info = {
                "name": name,
                "picture": image,
                "about": "TEST I show notes that are currently popular",
                "lud16": dvm_config.LN_ADDRESS,
                "supportsEncryption": False,
                "acceptsNutZaps": False,
                "personalized": False,
                "amount": create_amount_tag(cost),
                "nip90Params": {
                    "max_results": {
                        "required": False,
                        "values": [],
                        "description": "The number of maximum results to return (default currently 200)"
                    }
                }
            }

        nip89config = NIP89Config()
        nip89config.DTAG = check_and_set_d_tag(
                identifier,
                name,
                dvm_config.PRIVATE_KEY,
                nip89info["picture"]
            )

        nip89config.CONTENT = json.dumps(nip89info)
        nip89config.KIND = EventDefinitions.KIND_NIP90_CONTENT_DISCOVERY
        nip89config.NAME = name
        nip89config.PK = dvm_config.PRIVATE_KEY

        options = {
            "max_results": 200,
            "db_name": "db/test_content_discovery", 
            "db_since": 3600 * 24 * 30, # last 30 days
            "max_db_size" : 1024,
            "personalized": False
        }

        dvm = await build_test(
            name,
            dvm_config,
            nip89config,
            None,
            admin_config,
            options
        )

        dvm.run(True)

    except ValueError as e:
        print(f"Error executing DVM: {e}")


if __name__ == '__main__':
    env_path = Path('.env')
    if not env_path.is_file():
        with open('.env', 'w') as f:
            print("Writing new .env file")
            f.write('')
    if env_path.is_file():
        print(f'loading environment from {env_path.resolve()}')
        dotenv.load_dotenv(env_path, verbose=True, override=True)
    else:
        raise FileNotFoundError(f'.env file not found at {env_path} ')

    asyncio.run(configure_and_start_DVM())
