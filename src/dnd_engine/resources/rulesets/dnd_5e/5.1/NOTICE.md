# SRD 5.1 Attribution

This work includes material taken from the System Reference Document 5.1
("SRD 5.1") by Wizards of the Coast LLC and available at
https://dnd.wizards.com/resources/systems-reference-document.

The SRD 5.1 is licensed under the Creative Commons Attribution 4.0
International License available at
https://creativecommons.org/licenses/by/4.0/legalcode.

## What was changed

The packaged JSON in this directory is a transformed, abbreviated extract
of the SRD 5.1 source material: only selected closed-form fields (name,
ability scores, armor class, damage dice, damage type, damage modifier,
attack bonus, weapon properties, identifiers) were taken from the source
and re-expressed as JSON. No SRD prose, flavor text, or other narrative
content is reproduced here.

## Project ruleset identity

Ruleset `dnd_5e` in this project means classic Dungeons & Dragons 5th
Edition (2014 rules), i.e. SRD 5.1 — not SRD 5.2.x / the 2024 ("5.5e")
revision. Ruleset version for this data: `5.1`.

The `goblin` stat block fields packaged here (Armor Class 15; Ability
Scores Strength 8, Dexterity 14, Constitution 10, Intelligence 10, Wisdom
8, Charisma 8; Scimitar attack: +4 to hit, 1d6 + 2 slashing damage) were
verified against the official SRD 5.1 Goblin stat block before being
packaged. The Goblin's Shortbow attack is intentionally not packaged: it
is a ranged action, and this project's Monster attack contract does not
yet model range/reach. `goblin.attacks` therefore represents the subset
of the Goblin's SRD actions this project's current minimal Definition
contract supports, not a full transcription of its stat block.

The `dagger` weapon fields packaged here (damage 1d4 piercing; properties
finesse, light, thrown) were verified against the official SRD 5.1 Dagger
weapon table entry before being packaged. Range, cost, and weight are not
packaged: the current `WeaponDefinition` Domain contract has no fields for
them.
