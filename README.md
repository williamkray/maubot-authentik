this is a [maubot](https://github.com/maubot/maubot) plugin which interacts with Authentik APIs to manage invitations
via your pre-configured invitation enrollment flow. if you do not know what that means, this bot is not for you.

modify the config to point to your authentik deployment, generate and include an admin user API token to authenticate, let it rip.

note: you MUST include the flow UUID you want to associate with your invitation generation. in order to find this:

1. create a temporary invitation in the Authentic admin interface using the correct flow
2. open the API panel, and then click the link to browse the API Browser interface
3. run a GET on the /stages/invitation/invitations/ endpoint to view the details of your temporary invitation, you will
   find your flow UUID in the `response['results']['flow']` path.

there may be a simpler way to do this, but this worked for me.

once your bot is running, simply use the command

    !ak invite John Doe

to generate an invitation link with some generic text you can copy-paste when sharing it with your invitee!

to list all outstanding invitation links:

    !invite list

this bot now also includes a web endpoint for users to use instead of having to remember a bot command! it is assumed that the maubot instance running this bot is behind Authentik forwardauth proxy, and is correctly passing headers to the web endpoint. if you set that up, you can safely enable the web endpoint in this plugin's config.

the web endpoint `/generate` can be found at the plugin path defined in your maubot config. by default this will be:

    https://<yourpublicendpoint.tld>/_matrix/maubot/plugin/<yourbotinstance>/generate