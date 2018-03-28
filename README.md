## Podcast Player
Listen to episodes of your favourite podcasts

## Description
Select your favourite podcasts in the home.mycroft.ai settings and listen to episodes from those podcasts.
You can also check with Mycroft if there are any new episodes available from your chosen podcasts.

You can now also scroll through all episodes of your chosen podcasts.

### Setup
You can enter your chosen podcasts into the Skills Settings section of the home.mycroft.ai site.
Here you have space to store 3 podcasts. For each one you need to enter a trigger word and the feed
url for the podcast.
 - The trigger word can be a word of your choice that will usually be just the name
of the podcast (If the podcast has an unusual name like "The Nerdist" that Mycroft nay have difficulties understanding,
you can change the trigger word to something clearer like "Nerd").
 - The feed url is a url that can usually be found on the podcasts website under the RSS logo.

## Examples

Play podcast episodes:
* "play the podcast reply all"
* "put on the podcast linux unplugged"

Check the name of the latest episodes:
* "check for new episodes"
* "what is the latest episode of late night linux?"

## Credits
James Poole

## Current state
Working features:
 - Listen to any episode episode of your chosen podcast
 - Use the settings in the home.mycroft.ai site to choose 3 podcasts
 - Check for what the most recent episodes are titled

Known issues:
 - Currently I have not been able to get this to work with streams that require https. The mycroft audio service currently does not work with https streams so this is a limiting factor at the moment.
 - Not sure how this skill co-operates with other podcast skills
 - If a word like "News" is used as the trigger word, it may clash with another skill. If this happens change the trigger word to something that avoids the clash word
