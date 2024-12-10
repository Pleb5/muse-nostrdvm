# Manual List of known relays we can not write to. It's optional, but this way we avoid
# even trying to send to them, avoiding potential errors or delays on the way.


AVOID_OUTBOX_RELAY_LIST = ["wss://nos.lol", "wss://nostr.fmt.wiz.biz", "wss://nostrelay.yeghro.site", "wss://nostr.wine",
                           "wss://filter.nostr.wine", "wss://relay.lightwork.space", "wss://onchain.pub",
                           "wss://nostr21.com", "wss://nostr.bitcoiner.social", "wss://nostr.orangepill.dev",
                           "wss://brb.io", "wss://relay.nostr.ch", "wss://nostr.rock", "wss://nostr.sandwich.farm",
                           "wss://nostr.onsats.org", "wss://nostr-pub.semisol.dev", "wss://no.str.cr",
                           "wss://nostr.zebedee.cloud", "wss://blg.nostr.sx", "wss://relay.nostr.ai",
                           "wss://nostr.600.wtf", "ws://umbrel.local:4848", "wss://192.168.1.52:5051",
                           "wss://nostrvista.aaroniumii.com", "wss://https//nostr.einundzwanzig.space",
                           "wss://nostr.localhost.re", "wss://shopstr.store", "wss://th1.nostr.earnkrub.xyz",
                           "wss://relay.lnpay.me", "wss://relay.snort.social", "wss://relay.minds.com/nostr/v1/ws",
                           "ws://elitedesk:4848", "wss://wot.nostr.net", "wss://blg.nostr.sx",
                           "wss://nostr-pub.semisol.dev", "wss://mostr.mostr.pub", "wss://relay.mostr.pub",
                           "wss://minds.com", "wss://nostr.leximaster.com", "wss://th2.nostr.earnkrub.xyz",
                           "wss://relay.zerosatoshi.xyz", "wss://bouncer.minibolt.info",
                           "wss://yabu.me", "wss://relay.yozora.world", "wss://filter.nostr.wine/?global=all",
                           "wss://eden.nostr.land", "wss://relay.otherstuff.fyi",
                           "wss://relay.orangepill.ovh", "wss://nostr.jcloud.es", "wss://af.purplerelay.com",
                           "wss://za.purplerelay.com", "ws://192.168.18.7:7777", "wss://nostr.fediverse.jp",
                           "wss://relay.nostrich.land", "wss://relay.nostrplebs.com", "wss://relay.nostrich.land",
                           "ws://elitedesk.local:4848", "wss://nrelay-jp.c-stellar.net", "wss://blastr.f7z.xyz",
                           "wss://rss.nos.social", "wss://atlas.nostr.land", "wss://puravida.nostr.land",
                           "wss://nostr.inosta.cc", "wss://relay-jp.nostr.wirednet.jp",
                           "wss://relay.orangepill.dev", "wss://no.str.cr", "wss://nostr.milou.lol",
                           "wss://relay.nostr.com.au", "wss://nostrelites.com", "wss://sfr0.nostr1.com",
                           "wss://puravida.nostr.land", "wss://atlas.nostr.land", "wss://nostr-pub.wellorder.net",
                           "wss://relay.current.fyi", "wss://nfrelay.app",
                           "wss://nostr.thesamecat.io", "wss://nostr.plebchain.org", "wss://relay.noswhere.com",
                           "wss://nostr.uselessshit.co", "wss://tictac.nostr1.com", "wss://abcdefg20240104205400.xyz/v1",
                           "wss://bitcoiner.social", "wss://relay.stoner.com", "wss://nostr.l00p.org",
                           "wss://relay.nostr.ro", "wss://nostr.kollider.xyz",
                           "wss://relay.valera.co", "wss://relay.austrich.net", "wss://relay.nostrich.de",
                           "wss://nostr.azte.co", "wss://nostr-relay.schnitzel.world",
                           "wss://relay.nostriches.org", "wss://happytavern.co", "wss://onlynotes.lol",
                           "wss://offchain.pub", "wss://purplepag.es", "wss://relay.plebstr.com",
                           "wss://poster.place/relay", "wss://relayable.org", "wss://bbb.santos.lol",
                           "wss://relay.bitheaven.social", "wss://theforest.nostr1.com", "wss://at.nostrworks.com",
                           "wss://relay.nostrati.com", "wss://purplerelay.com", "wss://hist.nostr.land",
                           "wss://creatr.nostr.wine", "ws://localhost:4869", "wss://pleb.cloud",
                           "wss://pyramid.fiatjaf.com", "wss://relay.nos.social", "wss://nostr.thank.eu",
                           "wss://inbox.nostr.wine", "wss://relay.pleb.to", "wss://welcome.nostr.wine",
                           "wss://relay.nostrview.com", "wss://nostr.land", "wss://eu.purplerelay.com",
                           "wss://xmr.usenostr.org", "wss://nostr-relay.app", "ws://umbrel:4848", "wss://umbrel:4848",
                           "wss://fiatjaf.com", "wss://nostr-relay.wlvs.space", "wss://relayer.fiatjaf.com",
                           "wss://nostr.yuv.al", "wss://relay.nostr.band", "wss://nostr.massmux.com",
                           "wss://nostr-01.bolt.observer", "wss://nostr1.tunnelsats.com", "wss://relay.nostr.ch",
                           "wss://relay.nostr.io", "wss://nostr.thank.eu", "wss://nostr.bitcoinplebs.de",
                           "wss://adult.18plus.social", "wss://bostr.online", "wss://relay.current.fyi",
                           "wss://nosdrive.app/relay", "wss://studio314.nostr1.com", "wss://relay.nostrbr.online",
                           "wss://relay.0xchat.com", "wss://lightning.benchodroff.com/nostrclient/api/v1/relay",
                           "wss://relay.nostreggs.io", "wss://relay.blackbyte.nl", "ws://localhost:8080",
                           "wss://127.0.0.1:4869", "wss://sendit.nosflare.io",
                           "wss://astral.ninja", "wss://nostr.libertasprimordium.com", "wss://relay.shitforce.one",
                           "wss://nostr.cro.social", "wss://datagrave.wild-vibes.ts.net/nostr", "wss://nostr01.sharkshake.net",
                           "wss://relay.nostreggs.io", "wss://nostr.rocks", "wss://groups.0xchat.com",
                           "wss://bostr.lecturify.net", "wss://dave.st.germa.in/nostr",
                           "wss://dvms.f7z.io", "wss://nostr.social", "wss://i.nostr.build",
                           "wss://teemie1-relay.duckdns.org", "wss://newperspectives.duckdns.org",
                           "wss://nostrs.build", "wss://relay.hllo.live", "wss://relay-pub.deschooling.us",
                           "wss://nostr.sandwich.farm", "wss://nostr.lol", "wss://nostr.developer.li",
                           "wss://paid.spore.ws", "ws://relay.damus.io",
                           "ws://ofotwjuiv7t6q4azt2fjx3qo7esglmxdeqmh2qvdsdnxw5eqgza24iyd.onion", "wss://r.kojira.io",
                           "wss://nostr-relay.h3z.jp", "wss://relay.yozora.world",
                           "wss://nostr.0xtr.dev", "wss://purplepeg.es", "wss://nostr.mutinywallet.com",
                           "wss://nostr.zebedee.cloud", "wss://relay.wikifreedia.xyz", "wss://relay.exit.pub",
                           "wss://njump.mecheck", "wss://relay.nostr.band", "wss://nostr.kollider.xyz",
                           "wss://fog.dedyn.io", "wss://relay.current.fyi",
                           "wss://momostr.pink", "wss://nostr.bitcoinlighthouse.de", "wss://140.f7z.io",
                           "wss://relay.nostrcheck.me", "wss://relay.mostr.pub", "wss://purplepag.es",
                           "wss://nostr.bitcoiner.social", "wss://relay.galtsgulch.cc",
                           "ws://oxtrdevav64z64yb7x6rjg4ntzqjhedm5b5zjqulugknhzr46ny2qbad.onion",
                           "wss://relay.f7z.io", "wss://nostr-relay.h3z.jp", "wss://nfrelay.app",
                           "wss://r.kojira.io", "wss://jp-relay-nostr.invr.chat",
                           "wss://nostream-production-5895.up.railway.app",
                           "ws://127.0.0.1:4869", "wss://sign.siamstr.com", "wss://relay.hash.stream",
                           "wss://pablof7z.nostr1.com", "wss://nostr.beckmeyer.us", "wss://pow.hzrd149.com",
                           "wss://relay.nostrss.re", "wss://relay.nostr.bg", "ws://bugman.mguy.net:4848",
                           "wss://nostr-2.zebedee.cloud", "wss://nostr.lorentz.is", "wss://zap.nostr1.com",
                           "wss://onchain.pub", "wss://relay.nostr.info", "wss://relay.chicagoplebs.com",
                           "wss://relay.current.fyi", "wss://relay.stemstr.app", "wss://nostr.zenon.info",
                           "ws://localhost:7777", "wss://nostr.fmt.wiz.biz", "wss://nostrich.friendship.tw",
                           "wss://public.relaying.io", "wss://relay.me3d.app", "wss://dreamofthe90s.nostr1.com",
                           "wss://lnbits.eldamar.icu/nostrrelay/relay", "wss://nostr.olwe.link",
                           "wss://nostr.cheeserobot.org", "wss://nostr-relay.nokotaro.com", "wss://premium.primal.net"





                           ]
