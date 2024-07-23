from __future__ import annotations
from typing import Any, Dict, Optional, Type, Tuple


import json
import phonenumbers
import traceback

from loguru import logger
from pydantic.v1 import BaseModel

from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import ActionConfig as VocodeActionConfig
from vocode.streaming.models.actions import ActionInput, ActionOutput

from datetime import datetime

from twilio_sms import send_text_through_twilio

_SUBMIT_HEALTH_APPOINTMENT_INFO_ACTION_DESCRIPTION = """
Inputs a key value pair to the health care appointment form.
(SubmitHealthAppointmentInfoAction)

"""


class SubmitHealthAppointmentInfoParameters(BaseModel):
    payload: Dict[str, Any]

class SubmitHealthAppointmentInfoResponse(BaseModel):
    success: bool
    info: str
    next_step: str

def years_since(date_string):
    # Parse the date string into a datetime object
    given_date = datetime.strptime(date_string, "%Y-%m-%d")
    
    # Get the current date
    current_date = datetime.now()
    
    # Calculate the difference in years
    years_difference = current_date.year - given_date.year
    
    # Adjust for partial years
    if (current_date.month, current_date.day) < (given_date.month, given_date.day):
        years_difference -= 1

    return years_difference

class HealthAppointmentScheduler(BaseModel):
    scheduled_appointments_status: Dict[HealthAppointmentInfoContainer, str]

class HealthAppointmentInfoContainer(BaseModel):
    # openapi 3.1?
    input_schema = {
        'type': 'object',
        'properties': {
            'patient_name': {
                'type': 'string',
                'description': 'name of the patient',
            },
            'patient_dob': {
                'type': 'string',
                'format': 'date',
                'description': 'Date of birth for the patient.'
            },
            'insurance_info_payer_name': {
                'type': 'string',
                'description': 'insurance payer for patient. Examples include Aetna, Medicare Kaiser, etc',
            },
            'insurance_info_payer_id': {
                'type': 'string',
                'description': 'insurance payer id.',
            },
            'referral_to_physician': {
                'type': 'string',
                'description': 'The name of which doctor the patient has been referred to, if any.',
            },
            'reason_for_visit': {
                'type': 'string',
                'description': 'Why they are coming to visit.',
            },
            'patient_address': {
                'type': 'string',
                'description': 'patient address.',
            },
            'patient_phone_number': {
                'type': 'string',
                'description': 'patient phone number.',
            },
            'appointment_id': {
                'type': 'string',
                'description': 'appointment id. Before the first time asking for this information use *see_appointment_availability so that the user can know which appointment to pick.',
            },
            'appointment_physician_id': {
                'type': 'string',
                'description': 'appointment physician id.',
            },
            'appointment_physician_name': {
                'type': 'string',
                'description': 'appointment physician name.',
            },
            'appointment_time': {
                'type': 'string',
                'description': 'appointment time.',
            },
            'appointment_address': {
                'type': 'string',
                'description': 'appointment address.',
            },
            'send_text': {
                'type': 'boolean',
                'description': 'If a text should be sent.',
            },
            '*see_next_step': {
                'type': 'string',
                'description': 'Input will be ignored, but returns the next step.',
            },
            '*see_appointment_availability': {
                'type': 'string',
                'description': 'Input will be ignored, but returns a list of available physicians and times.',
            },
            '*validate_all_and_submit_if_valid': {
                'type': 'string',
                'description': 'Input will be ignored, but returns if the appointment scheduling has been finished. Validates all fields, autofills fields if necessary, and submits if valid.',
            }
        }
    }
    input_schema_helper_info = {
        'stage_1_fields': [
            'patient_name',
            'patient_dob',
            'insurance_info_payer_name',
            'insurance_info_payer_id',
            'referral_to_physician',
            'reason_for_visit',
            'patient_address',
            'patient_phone_number',
        ],
        'stage_1_required_fields': [
            'patient_name',
            'patient_dob',
            'reason_for_visit',
            'patient_phone_number'
        ],
        'stage_2_fields': [
            'appointment_number',
            'appointment_id',
            'appointment_physician_id',
            'appointment_physician_name',
            'appointment_time',
            'appointment_address',
        ],
        'stage_2_required_fields': [
            'appointment_id',
        ],
        'stage_3_fields': [
            'send_text',
        ],
        'stage_3_required_fields': [
            'send_text',
        ],
        'field_stages': ['stage_1_fields', 'stage_2_fields', 'stage_3_fields'],
        'required_field_stages': ['stage_1_required_fields', 'stage_2_required_fields', 'stage_3_required_fields'],
        'fields_to_not_validate_or_send': ['input_schema', 'input_schema_helper_info'],
    }
    patient_name: Optional[str]
    patient_dob: Optional[str]
    insurance_info_payer_name: Optional[str]
    insurance_info_payer_id: Optional[str]
    referral_to_physician: Optional[str] 
    reason_for_visit: Optional[str] 
    patient_address: Optional[str]
    patient_phone_number: Optional[str] 
    appointment_number: Optional[str] 
    appointment_id: Optional[str] 
    appointment_physician_id: Optional[str] 
    appointment_physician_name: Optional[str] 
    appointment_time: Optional[str] 
    appointment_address: Optional[str] 
    send_text: Optional[bool]


    def get_required_field_names(self):
        field_names = []
        for required_field_stage in self.input_schema_helper_info['required_field_stages']:
            for required_field in self.input_schema_helper_info[required_field_stage]:
                field_names.append(required_field)
        return field_names
    
    def field_info_str(self):
        out = []
        for field_stage in self.input_schema_helper_info['field_stages']:
            out.append({field: getattr(self, field) for field in self.input_schema_helper_info[field_stage]})
        return json.dumps({'appointment_info': out}, indent=2)

    def validate_key_and_submit_if_valid(self, payload: Dict, health_appointment_scheduler: HealthAppointmentScheduler) -> tuple[bool, str, str]:
        keys = list(payload.keys())
        key = keys[0] if keys else ''
        value = payload[key]
        next_step = ''

        if len(key) > 0 and key[0] == '*':
            return self.special_fields(key, health_appointment_scheduler)
        
        if len(keys) > 1:
            return (False, f'multiple keys found: {keys}', 'please input only one key at a time')
        
        next_step += 'repeat back to the caller the value inputted, and confirm that\'s correct. To save and submit, use *validate_all_and_submit_if_valid'

        if key == 'patient_name':
            if ' ' not in value:
                # how does this work for chinese?
                return (False, 'patient should give first and last name', next_step)
            setattr(self, key, value)
            return (True, key + ' is valid', next_step + ' note: Spell back the name inputted.')
        if key == 'patient_dob':
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return (False, 'error parsing date: patient should give their full date of birth, month, day and year in the format YYYY-MM-DD .', next_step + ' If the month, day, year are present, but the format is wrong, try reinputting ')
            try:
                age = years_since(value)
                if age < -1 or age > 150:
                    return (False, 'calculated age was {} which is invalid'.format(age), next_step)
            except ValueError:
                return (False, 'error calculating years of age. ', next_step)
            setattr(self, key, value)
            return (True, key + ' is valid', next_step)
        if key == 'patient_phone_number':
            parsed_number = None
            try:
                parsed_number = phonenumbers.parse(value, "US")
            except phonenumbers.phonenumberutil.NumberParseException:
                return (False, 'could not parse provided number: {}'.format(value), next_step + ' please retry.')
            
            if not phonenumbers.is_valid_number(parsed_number):
                return (False, 'number provided is not valid: {}'.format(value), next_step + ' please retry.')
            
            formatted_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)

            setattr(self, key, formatted_number)
            return (True, 'The parsed number that will be used is {}'.format(formatted_number), next_step + ' If the user doesn\t say the number is correct, tell the user for international numbers a plus sign should be added in front (E.164 format).')
        if key in self.input_schema['properties']:
            # no validation
            setattr(self, key, value)
            return (True, key + ' is valid', next_step)
        # not found
        return (False, key + ' not found', next_step)
    
    def available_appointments_list(self) -> list[Dict[str, str]]:
        return [
            {
                'appointment_number': '1',
                'appointment_id': 'appt_id_155121',
                'appointment_physician_id': 'phys_id_124512',
                'appointment_physician_name': 'Dr. Nickel Baker',
                'appointment_time': '2:00 PM Saturday July 20',
                'appointment_address': '123 St Clinic, 123 123 St',
            },
            {
                'appointment_number': '2',
                'appointment_id': 'appt_id_128841',
                'appointment_physician_id': 'phys_id_124512',
                'appointment_physician_name': 'Dr. Nickel Baker',
                'appointment_time': '3:00 PM Saturday July 20',
                'appointment_address': '123 St Clinic, 123 123 St',
            },
            {
                'appointment_number': '3',
                'appointment_id': 'appt_id_166341',
                'appointment_physician_id': 'phys_id_124512',
                'appointment_physician_name': 'Dr. Nickel Baker',
                'appointment_time': '4:00 PM Saturday July 20',
                'appointment_address': '123 St Clinic, 123 123 St',
            },
        ]
    
    def special_fields(self, key: str, health_appointment_scheduler: HealthAppointmentScheduler)  -> tuple[bool, str, str]:
        if key == '*see_next_step':
            return (True, 'seeing next step', 'if any required fields are missing, ask the user for information.')
        if key == '*see_appointment_availability':
            return (True, f"""available appointments list: {self.available_appointments_list()}""", 'help the user pick out an appointment. Don\'t repeat verbatim, give important details like name and time.')
        if key == '*validate_all_and_submit_if_valid':

            if self in health_appointment_scheduler.scheduled_appointments_status and health_appointment_scheduler.scheduled_appointments_status[self] == 'scheduled':
                return (False, 'This appointment has already been successfully submitted, ')

            errors = []
            for required_field_stage in self.input_schema_helper_info['required_field_stages']:
                for required_field in self.input_schema_helper_info[required_field_stage]:
                    if getattr(self, required_field) is None:
                        errors.append(f'required field {required_field} is None')
            
            for field_name, field_value in vars(self).items():
                if field_name in self.input_schema_helper_info['fields_to_not_validate_or_send']:
                    continue
                if field_name not in self.get_required_field_names() and field_value is None:
                    continue
                if field_value is None:
                    errors.append(f'field {field_name} is required, ask the user for info. ')
                success, info_string, next_step = self.validate_key_and_submit_if_valid({field_name: field_value}, health_appointment_scheduler)
                if not success:
                    errors.append(f'field {field_name} with value {field_value} did not validate: {info_string}')
            
            if errors:
                return (False, f'errors found: {errors}', 'Ask the user for information to fix the errors, don\'t end the call')
            else:
                # autofill:
                if self.appointment_id:
                    filtered_appointments = [appt for appt in self.available_appointments_list() if appt['appointment_id'] == self.appointment_id]
                    if len(filtered_appointments) > 0:
                        for field, value in filtered_appointments[0].items():
                            if not getattr(self, field):
                                setattr(self, field, value)

                if self.send_text:
                    try:
                        send_text_through_twilio(self.patient_phone_number, f'Your appointment details:\n{self.field_info_str()}')
                    except Exception:
                        logger.error(traceback.format_exc())
                        return (False, 'Could not send confirmation text', 'please retry')
                health_appointment_scheduler.scheduled_appointments_status[self] = 'scheduled'
                return (True, '', 'Tell the user "Information successfully submitted. A confirmation text has been sent if the option was selected.".')
        return (False, f'special field: {key} not found', 'please retry')
    
    # only want objects to be the same if they are the same instance
    def __eq__(self, other):
        if isinstance(other, HealthAppointmentInfoContainer):
            # Objects are equal if they have the same memory address
            return id(self) == id(other)
        return False

    def __hash__(self):
        # Hash based on the memory address (id)
        return id(self)

HealthAppointmentScheduler.update_forward_refs()

class SubmitHealthAppointmentInfoActionConfig(
    VocodeActionConfig,
    type="action_imput_health_appointment_info"  # type: ignore
):
    health_appointment_info_container: HealthAppointmentInfoContainer
    health_appointment_scheduler: HealthAppointmentScheduler
    temp: Optional[list]

    @classmethod
    def type_string(cls):
        return 'action_imput_health_appointment_info'

    def action_attempt_to_string(self, input: ActionInput) -> str:
        assert isinstance(input.params, SubmitHealthAppointmentInfoParameters)
        # use repr to escape strings if necessary
        return f"Attempting to set key: {repr(input.params.key)} to val: {repr(input.params.val)}"

    def action_result_to_string(self, input: ActionInput, output: ActionOutput) -> str:
        assert isinstance(output.response, SubmitHealthAppointmentInfoResponse)
        if output.response.success:
            action_description = f"info: {repr(output.response.info)} Next step: {repr(output.response.next_step)}"
        else:
            action_description = f"Error: {repr(output.response.info)} Next step: {repr(output.response.next_step)}"
        return action_description

class SubmitHealthAppointmentInfo(
    BaseAction[
        SubmitHealthAppointmentInfoActionConfig,
        SubmitHealthAppointmentInfoParameters,
        SubmitHealthAppointmentInfoResponse,
    ]
):
    # from taking a look at execute_external_action.py
    speak_on_send: bool = False
    speak_on_recieve: bool = True
    description: str = _SUBMIT_HEALTH_APPOINTMENT_INFO_ACTION_DESCRIPTION
    parameters_type: Type[SubmitHealthAppointmentInfoParameters] = SubmitHealthAppointmentInfoParameters
    response_type: Type[SubmitHealthAppointmentInfoResponse] = SubmitHealthAppointmentInfoResponse

    def __init__(
        self,
        action_config: SubmitHealthAppointmentInfoActionConfig,
    ):
        super().__init__(
            action_config,
            quiet=not self.speak_on_recieve,
            should_respond="always" if self.speak_on_send else "never",
            is_interruptible=False,
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'payload': self.action_config.health_appointment_info_container.input_schema
            },
        }

    async def _end_of_run_hook(self) -> None:
        """This method is called at the end of the run method. It is optional but intended to be
        overridden if needed."""
        pass

    async def run(
        self, action_input: ActionInput[SubmitHealthAppointmentInfoParameters]
    ) -> ActionOutput[SubmitHealthAppointmentInfoResponse]:
        if action_input.user_message_tracker is not None:
            await action_input.user_message_tracker.wait()

        # can also return a different state if the bot is interrupted:
        # if self.conversation_state_manager.transcript.was_last_message_interrupted():
        #     logger.info("Last bot message was interrupted")
        #     return ActionOutput(
        #         action_type=action_input.action_config.type,
        #         response=SubmitHealthAppointmentInfoResponse(success=False, info='', next_step='please retry'),
        #     )

        try:
            success_bool, info_string, next_step = self.action_config.health_appointment_info_container \
                .validate_key_and_submit_if_valid(action_input.params.payload, self.action_config.health_appointment_scheduler)
        except Exception as e:
            logger.error(traceback.format_exc())
            return ActionOutput(
                action_type=action_input.action_config.type,
                response=SubmitHealthAppointmentInfoResponse(success=False, info = 'Error: an application error has occurred', next_step = 'retry?'),
            )

        await self._end_of_run_hook()
        return ActionOutput(
            action_type=action_input.action_config.type,
            response=SubmitHealthAppointmentInfoResponse(success=success_bool, info = info_string, next_step = next_step),
        )
