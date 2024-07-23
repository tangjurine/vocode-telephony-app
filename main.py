# Standard library imports
import os
import sys

from dotenv import load_dotenv

# Third-party imports
from fastapi import FastAPI, Request
from loguru import logger
from pyngrok import ngrok

# Local application/library specific imports
from submit_health_appointment_info import SubmitHealthAppointmentInfoActionConfig, HealthAppointmentInfoContainer, HealthAppointmentScheduler
from speller_agent import SpellerAgentFactory, SpellerAgentConfig

from vocode.logging import configure_pretty_logging
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.server.base import TelephonyServer, TwilioInboundCallConfig
from vocode.streaming.action.end_conversation import EndConversationVocodeActionConfig

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
load_dotenv()

configure_pretty_logging()

app = FastAPI(docs_url=None)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hello, this line schedules appointments for Dr. Tang's Clinic. Would you like to make an appointment?"),
                # todo: maybe the prompt should be walking the caller through
                # a scheduling application, the agent should keep
                # trying to input things into the form and see the errors
                # he's getting back, and tell the user about it.
                #prompt_preamble="Collect the patient's name and date of birth, and then end the call.",
                #"""
                #    Help the caller schedule a doctor's appointment.
                #    Keep using the submit info action until there are no errors.
                # """
                prompt_preamble=f"""
                    Help the caller schedule a doctor's appointment.
                    
                    Collect the following fields from the caller: {repr(HealthAppointmentInfoContainer().input_schema['properties'])},
                    and use the {SubmitHealthAppointmentInfoActionConfig.type_string()} each time information is given.
                    If the user has already given pieces of information, and
                    the {SubmitHealthAppointmentInfoActionConfig.type_string()} was not called, call
                    the {SubmitHealthAppointmentInfoActionConfig.type_string()} multiple times for each piece
                    of information. Don't call the action once with multiple pieces of
                    information.

                    The fields that start with *, for example *see_next_step, are not required and should
                    not be collected from the caller. They should be used to check that the form from
                    {SubmitHealthAppointmentInfoActionConfig.type_string()} is in a valid state, and to
                    collect data, etc.

                    Also, see which fields are required in {HealthAppointmentInfoContainer().input_schema_helper_info}.

                    If the {SubmitHealthAppointmentInfoActionConfig.type_string()} function is successful, let the user know.
                    If the {SubmitHealthAppointmentInfoActionConfig.type_string()} function gives an error, also let the user know,
                    and try to work through the error with the user.
                    If the {SubmitHealthAppointmentInfoActionConfig.type_string()} has a next step, 
                    such as repeating the info back to confirm, or spelling out the info, do it, unless the user asks not to.

                    Don't say YYYY-MM-DD when referring to date of birth, say date of birth.

                    When spelling or saying individual letters, output what you want to say
                    with a period and a space between each letter. Also, turn spaces into the word space.
                    For example, testing should become: t. e. s. t. i. n. g. 
                    Also, Apple Pie should become: A. p. p. l. e. space P. i. e.

                    If the user says 'yeah', or 'uhh', consider that they are trying to
                    start a sentence, and wait before trying to say something.

                    Don't list out all the required fields more than once or unless prompted.

                    After inputting a field to {SubmitHealthAppointmentInfoActionConfig.type_string()},
                    confirm with the user the field submitted by repeating the info back, and ask if that is correct (unless the field is special/starts with a *).

                    If a field is not listed as required in {HealthAppointmentInfoContainer().get_required_field_names()}, don't tell the user the field is needed or required.
                    But do ask for the field, if the information is not already present.

                    After getting the required fields for each stage, move to the next stage.
                    Please get appointment information from {SubmitHealthAppointmentInfoActionConfig.type_string()} with the field '*see_appointment_availability',
                    and not from the user, other than the user picking which appointment from the list.

                    If a field is not required, tell the caller it is optional and they can continue without it.
                    Providing a non-required field now can save time at the clinic.

                    Please keep trying to run {SubmitHealthAppointmentInfoActionConfig.type_string()} with the field '*validate_all_and_submit_if_valid'
                    and follow the steps to successfully submit.

                    Don't tell the user their appointment is confirmed until successfully running
                    {SubmitHealthAppointmentInfoActionConfig.type_string()} with the field '*validate_all_and_submit_if_valid'.

                    After inputting a field, don't say 'confirmed', or 'scheduled', say the info was successfully validated.
                    
                    Get all required fields from each stage before moving to the next, i.e.,
                    don't ask the caller which appointment they'd like until they have
                    provided their name, reason for visit, etc.

                    Important: Before telling the user all the information is good and confirmed,
                    or before telling the user their appointment has been scheduled,
                    run {SubmitHealthAppointmentInfoActionConfig.type_string()} with the field '*validate_all_and_submit_if_valid'.

                    To submit the info inputted, use:
                    {SubmitHealthAppointmentInfoActionConfig.type_string()} with the field '*validate_all_and_submit_if_valid'

                    Important: no information will be saved, or submitted, unless the following is used:
                    {SubmitHealthAppointmentInfoActionConfig.type_string()} with the field '*validate_all_and_submit_if_valid'

                """,
                generate_responses=True,
                actions = [
                    EndConversationVocodeActionConfig(),
                    SubmitHealthAppointmentInfoActionConfig(
                        health_appointment_info_container=HealthAppointmentInfoContainer(),
                        health_appointment_scheduler=HealthAppointmentScheduler(scheduled_appointments_status={}))
                ]
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=SpellerAgentFactory(),
)

app.include_router(telephony_server.get_router())