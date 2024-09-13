this is a [maubot](https://github.com/maubot/maubot) plugin which interacts with Authentik APIs to manage invitations
via your pre-configured invitation enrollment flow. if you do not know what that means, this bot is not for you.

modify the config to point to your authentik deployment, generate and include and admin user API token to authenticate, let it rip.

once your bot is running, simply use the command

    !ak invite John Doe

to generate an invitation link with some generic text you can copy-paste when sharing it with your invitee!

to list all outstanding invitation links:

    !invite list

