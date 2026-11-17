# FMFN (Uutiset-repositorio)

Uutissivusto, jossa käyttäjä kokoaa omat kategoriansa valitsemistaan uutislähteistä ja hakusanoista.

## Työtapa

- Vastaa suomeksi, lyhyesti ja yksinkertaisesti.
- Tee muutokset ja tallenna (commit + push) suoraan kysymättä lupaa, ellei käyttäjä erikseen toisin mainitse.
- Kaikki työ tehdään `main`-haarassa. (`alalahteet`-haara on yhdistetty mainiin.)
- Älä tallenna repositorioon testikuvia, `__pycache__`-kansioita tai muita apu- ja välitiedostoja.

## Tiedostot

| Tiedosto | Tarkoitus | Kuka muokkaa |
|---|---|---|
| `index.html` | Koko sivusto (HTML, CSS ja JS samassa tiedostossa) | ihminen / Claude |
| `lahteet.json` | Luettelo kaikista lähteistä ja alalähteistä | ihminen / Claude |
| `oletus_lahteet.json` | Valmiit kategoriat, jotka viittaavat lähteisiin tunnuksilla | ihminen / Claude |
| `data/` | Haetut uutiset lähteittäin | vain robotti, älä muokkaa käsin |
| `skriptit/hae_lahteet.py` | Hakee uutiset `lahteet.json`:n perusteella `data/`-kansioon | |
| `skriptit/tarkista.py` | Testaa RSS-osoitteet ja päivittää `testattu`-kentät | |
| `.github/workflows/` | "Hae uutiset" (30 min välein ja käsin) ja "Tarkista lähteet" (käsin) | |

## Lähteen lisääminen

Käyttäjä antaa lähteen muodossa:

```
Lähteen nimi - alalähde + linkki
```

- Ei alalähdettä (esim. `Rumba + https://...`) → uusi päälähde omalla `rss`-kentällä. Siitä tulee uusi kansio `data/<lähde>/`.
- Alalähde mukana (esim. `Sky Sports - Tennis + https://...`) → lisää alalähteeksi olemassa olevalle päälähteelle, jolloin se menee sen valmiiseen kansioon. Jos päälähdettä ei vielä ole, luo se. Jos päälähteellä on oma `rss`, siirrä se ensin alalähteeksi (ks. säännöt alla).
- Lisää muutos suoraan `lahteet.json`:iin kysymättä. Kansiot ja tiedostot `data/`-kansioon luo robotti seuraavassa haussa.
- Jos linkki on tavallinen verkkosivu eikä RSS-syöte, käytä sivuston vastaavaa RSS-osoitetta, jos se tiedetään, ja kerro siitä käyttäjälle. Jos sama syöte on jo lähteissä, kerro se äläkä lisää kaksoiskappaletta.

Vastaus lähteiden lisäämisen jälkeen, lyhyesti, yksi rivi per lähde:

- 🟢 lisätty, ei lisätoimia.
- 🟡 lisätty, mutta vaatii lisätoimia. Jos voit korjata itse, korjaa ja kerro mitä teit. Muuten tarjoa ratkaisu.
- 🔴 ei lisätty, syy ja ehdotettu ratkaisu. Käyttäjä päättää.

Päälähde, jolla on oma RSS-osoite:

```json
{ "id": "hs", "nimi": "Helsingin Sanomat", "kieli": "fi", "rss": "https://...", "testattu": false }
```

Päälähde, jolla on alalähteitä (ei omaa `rss`-kenttää):

```json
{
 "id": "bbc", "nimi": "BBC", "kieli": "en",
 "alalahteet": [
  { "id": "news", "nimi": "News", "rss": "https://...", "testattu": false }
 ],
 "testattu": false
}
```

Säännöt:

- `id`: vain pienet kirjaimet a-z, numerot ja viivat. Ei alaviivaa, koska se erottaa tiedostonimissä lähteen ja alalähteen. Tunnuksen pitää olla yksilöllinen.
- Lähteellä on joko oma `rss` tai `alalahteet`, ei molempia. Jos lähteelle, jolla on oma `rss`, lisätään alalähde, siirrä sen oma osoite ensin alalähteeksi (esim. `uutiset`).
- `kieli` on `fi` tai `en`. Alalähde perii sen päälähteeltä, ellei sille anneta omaa kieltä.
- Uudelle osoitteelle `testattu: false`. Tämän ympäristön verkko ei pääse uutissivustoille, joten osoitteita ei voi testata täältä. Käyttäjä ajaa testin GitHubin Actions-välilehdeltä ("Tarkista lähteet").
- Pidä lähteet aakkosjärjestyksessä nimen mukaan. Alun "The" ohitetaan järjestämisessä.
- `vanha_id` lisätään vain, jos olemassa olevan syötteen tunnus muuttuu, jotta käyttäjien tallentamat kategoriat toimivat edelleen.
- Älä luo tiedostoja `data/`-kansioon käsin. Robotti luo ne seuraavassa haussa. Ajastettu haku toimii `main`-haarassa 30 minuutin välein, ja käyttäjä voi ajaa "Hae uutiset" myös käsin.
- Tarkista lopuksi, että `lahteet.json` on kelvollista JSONia ja että `oletus_lahteet.json`:n tunnukset löytyvät `lahteet.json`:sta.

## data-kansion rakenne

```
data/<lähde>/<lähde>.json             koko lähteen uutiset (kaikki alalähteet yhdessä)
data/<lähde>/<lähde>_<alalähde>.json  yhden alalähteen uutiset
```

Esimerkiksi `data/bbc/bbc.json` ja `data/bbc/bbc_news.json`. Lähteellä, jolla ei ole alalähteitä, on vain `data/<lähde>/<lähde>.json`. Sivu lataa koko lähteen tiedoston, kun käyttäjä on valinnut lähteen kaikki alalähteet, ja muuten vain valitut alalähteet. Tiedostonimien sääntö on sekä `hae_lahteet.py`:ssä (`feed_file`, `whole_file`) että `index.html`:ssä (`feedFile`, `wholeFile`), ja niiden pitää pysyä samoina.

## Git

- Repositorio on kloonattu matalana (shallow). Tallenna komennolla `git -c push.negotiate=true push origin <haara>`.
- Robotti tallentaa uutisia `main`-haaraan puolen tunnin välein. Hae siksi uusin versio ennen tallennusta: `git pull --rebase --depth=50 origin <haara>`.
