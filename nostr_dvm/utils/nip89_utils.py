import os
from hashlib import sha256
from pathlib import Path

import dotenv
from nostr_sdk import Tag, Keys, EventBuilder, Filter, Alphabet, PublicKey, Client, EventId, SingleLetterTag, Kind

from nostr_dvm.utils.definitions import EventDefinitions, relay_timeout
from nostr_dvm.utils.nostr_utils import send_event
from nostr_dvm.utils.print_utils import bcolors


class NIP89Config:
    DTAG: str = ""
    NAME: str = ""
    KIND: int = None
    PK: str = ""
    CONTENT: str = ""


def nip89_create_d_tag(name, pubkey, image):
    key_str = str(name + image + pubkey)
    d_tag = sha256(key_str.encode('utf-8')).hexdigest()[:16]
    return d_tag


async def nip89_announce_tasks(dvm_config, client):
    k_tag = Tag.parse(["k", str(dvm_config.NIP89.KIND.as_u16())])
    d_tag = Tag.parse(["d", dvm_config.NIP89.DTAG])
    keys = Keys.parse(dvm_config.NIP89.PK)
    content = dvm_config.NIP89.CONTENT
    event = EventBuilder(EventDefinitions.KIND_ANNOUNCEMENT, content).tags([k_tag, d_tag]).sign_with_keys(keys)
    eventid = await send_event(event, client=client, dvm_config=dvm_config)

    print(
        bcolors.BLUE + "[" + dvm_config.NIP89.NAME + "] Announced NIP 89 for " + dvm_config.NIP89.NAME + " (" + eventid.id.to_hex() + ")" + bcolors.ENDC)


async def fetch_nip89_parameters_for_deletion(keys, eventid, client, dvmconfig, pow=False):
    idfilter = Filter().id(EventId.from_hex(eventid)).limit(1)
    nip89events = await client.fetch_events([idfilter], relay_timeout)
    d_tag = ""
    if len(nip89events.to_vec()) == 0:
        print("Event not found. Potentially gone.")

    for event in nip89events.to_vec():
        print(event.as_json())
        for tag in event.tags().to_vec():
            if tag.as_vec()[0] == "d":
                d_tag = tag.as_vec()[1]
        if d_tag == "":
            print("No dtag found")
            return

        if event.author().to_hex() == keys.public_key().to_hex():
            if pow:
                print("Delete with POW, this might take a while, please wait until finished")
                await nip89_delete_announcement_pow(event.id().to_hex(), keys, d_tag, client, dvmconfig)
            else:
                await nip89_delete_announcement(event.id().to_hex(), keys, d_tag, client, dvmconfig)

            print("NIP89 announcement deleted from known relays!")
        else:
            print("Privatekey does not belong to event")


async def nip89_delete_announcement(eid: str, keys: Keys, dtag: str, client: Client, config):
    e_tag = Tag.parse(["e", eid])
    a_tag = Tag.parse(
        ["a", str(EventDefinitions.KIND_ANNOUNCEMENT.as_u16()) + ":" + keys.public_key().to_hex() + ":" + dtag])
    event = EventBuilder(Kind(5), "").tags([e_tag, a_tag]).sign_with_keys(keys)
    print(f"Deletion event: {event.as_json()}")
    await send_event(event, client, config)


async def nip89_delete_announcement_pow(eid: str, keys: Keys, dtag: str, client: Client, config):
    e_tag = Tag.parse(["e", eid])
    a_tag = Tag.parse(
        ["a", str(EventDefinitions.KIND_ANNOUNCEMENT.as_u16()) + ":" + keys.public_key().to_hex() + ":" + dtag])
    event = EventBuilder(Kind(5), "").tags([e_tag, a_tag]).pow(28).sign_with_keys(keys)
    print(f"POW event: {event.as_json()}")
    await send_event(event, client, config)


async def nip89_fetch_all_dvms(client):
    ktags = []
    for i in range(5000, 5999):
        ktags.append(str(i))

    filter = Filter().kind(EventDefinitions.KIND_ANNOUNCEMENT).custom_tag(SingleLetterTag.lowercase(Alphabet.K), ktags)
    events = await client.fetch_events([filter], relay_timeout)
    for event in events.to_vec():
        print(event.as_json())


async def nip89_fetch_events_pubkey(client, pubkey, kind):
    ktags = [str(kind.as_u16())]
    nip89filter = (Filter().kind(EventDefinitions.KIND_ANNOUNCEMENT).author(PublicKey.parse(pubkey)).
                   custom_tag(SingleLetterTag.lowercase(Alphabet.K), ktags))
    events = await client.fetch_events([nip89filter], relay_timeout)

    dvms = {}
    for event in events.to_vec():
        if dvms.get(event.author().to_hex()):
            if dvms.get(event.author().to_hex()).created_at().as_secs() < event.created_at().as_secs():
                dvms[event.author().to_hex()] = event
        else:
            dvms[event.author().to_hex()] = event

    # should be one element of the kind now
    for dvm in dvms:
        return dvms[dvm].content()


def check_and_set_d_tag(env_path, identifier, name, pk, imageurl):
    if not os.getenv("NIP89_DTAG_" + identifier.upper()):
        new_dtag = nip89_create_d_tag(name, Keys.parse(pk).public_key().to_hex(),
                                      imageurl)
        nip89_add_dtag_to_env_file(env_path, "NIP89_DTAG_" + identifier.upper(), new_dtag)
        print("Some new dtag:" + new_dtag)
        return new_dtag
    else:
        return os.getenv("NIP89_DTAG_" + identifier.upper())


def nip89_add_dtag_to_env_file(env_path, dtag, oskey):
    env_path = Path(env_path)
    if env_path.is_file():
        print(f'loading environment from {env_path.resolve()}')
        dotenv.load_dotenv(env_path, verbose=True, override=True)
        dotenv.set_key(env_path, dtag, oskey)


def create_amount_tag(cost=None):
    if cost is None:
        return "flexible"
    elif cost == 0:
        return "free"
    else:
        return str(cost)
