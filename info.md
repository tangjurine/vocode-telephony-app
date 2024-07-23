
My changes to setup steps:

Installed poetry and docker, used docker to run the server, etc,
and poetry to have source code that vscode can look at.

build (in same directory as this README) (after ngrok is up (see docs)):

docker build -t vocode-telephony-app . && docker-compose up


Debugging tips:

If twilio is not connecting to the server due to ngrok issues, try restarting
ngrok.

    Access the python env:
    (execute commands in directory)
    poetry shell
    python

    Couldn't manage to get debugging working, ended up logging
    http calls by putting the following into
    httpx._client.AsyncClient._send_single_request, in the python
    source files created by running poetry
    (so only shows up when running code locally/not with docker):
        logger.info(
            'HTTP Request: %s %s "%s %d %s" %s %s', # modified
            request.method,
            request.url,
            response.http_version,
            response.status_code,
            response.reason_phrase,
            request.headers.items(),  # modifed
            textwrap.indent(json.dumps(json.loads(request.content), indent=2), "    "),  # modifed
        )


Code issues:

In SubmitHealthAppointmentInfoActionConfig, 
if the response returned by the agent doesn't match the input schema,
my code causes a hard to catch exception to be thrown, and the agent
doesn't realize the issue/communicate to the caller the issue, and I'm
not sure how to fix this without modifying the library (but might be possible).

I didn't try playing around with different voices, so certain
phrases such as YYYY-MM-DD are said very quickly.

Sometimes I say 'ummm' before my sentence, and the library sometimes
sends a request/prompts the agent to start speaking too quickly.
The agent also doesn't adjust the delay when I'm having trouble, so
it can get very frustrating. - adjusted this by adding something to the prompt,
but now occasionally the agent stays silent, which is a bit better imo.

Not put all of my code into submit_health_appointment_info.py, etc.

Structure my code so that for each field, the agent can be configured
to do additional validation, like saying the field value or spelling
the field value out, rather than putting it in the prompt.

No tests... should have unit/integration tests?

Put extra actions into my one action class instead of making multiple actions,
because the setup would take too long.

Issues controlling bot without trying to change a lot of code:
sometimes the bot doesn't spell the name back.
sometimes the bot will require the user to give the date of birth in the format YYYY-MM-DD,
but the bot just needs to submit that info in that format.

Try refactoring the code to have less edge cases in the prompt/
have more logic in the actions prompts, so the bot performs better. 
But the bot doesn't seem to listen sometimes to instructions in the actions.

Refactor my code so that if an error in the validation/setting values on
the form is thrown, the bot doesn't throw an error, but reports the error to
the user.

Library issues:

For a class that overrides BaseAction.get_parameters_schema, the openAPI spec
can't contain oneOf, due to how vocode\streaming\agent\token_utils.py.format_schema
is implemented.

EndConversation has an _end_of_run_hook method,
but there is not a built in way to pass a _end_of_run_hook method from
the EndConversationVocodeActionConfig (need to write some code in the factory...)

Vocode BaseModel will clone fields that are lists and dicts, so can't 
rely on references to those objects.