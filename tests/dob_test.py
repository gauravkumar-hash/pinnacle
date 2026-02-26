import unittest
from pydantic import ValidationError
from routers.patient.auth import RegisterInput
from utils import sg_datetime

class TestRegisterInput(unittest.TestCase):

    def test_validate_dob_valid(self):
        today = sg_datetime.now().date()
        valid_dob = today.replace(year=today.year - 20)  # 20 years old
        input_data = {
            "session_id": "test_session_id",
            "name": "Test User",
            "date_of_birth": valid_dob,
            "nationality": "Singapore Citizen",
            "language": "English",
            "gender": "Male"
        }
        register_input = RegisterInput(**input_data)
        self.assertEqual(register_input.date_of_birth, valid_dob)

    def test_validate_dob_future_date(self):
        future_date = sg_datetime.now().date().replace(year=sg_datetime.now().year + 1)
        input_data = {
            "session_id": "test_session_id",
            "name": "Test User",
            "date_of_birth": future_date,
            "nationality": "Singapore Citizen",
            "language": "English",
            "gender": "Male"
        }
        
        with self.assertRaises(ValidationError) as context:
            # try:
            RegisterInput(**input_data)
            # except Exception as e:
            #     print(f"Error: {e}") 
            print("Context: ",context.exception)
            self.assertIn('1Date 123 of birth cannot be in the future 123', [err.get('msg') for err in context.exception.errors()])

        
        # with self.assertRaises(ValidationError):
        #     try:
        #         print("Data: ")
        #         data = RegisterInput(**input_data)
        #         print("Data: ",data)
        #         # RegisterInput.model_validate(**input_data)
        #     except ValidationError as e:
        #         print(f"Error1 {e}")
        #         print(f"Error2 {e.errors()[0].items()}")
        #         print(f"Error3 {[err.get('ctx').get('error') for err in e.errors()]}")
        #         print(f"Error4 {[err.get('msg') for err in e.errors()]}")

    # def test_validate_dob_underage(self):
    #     today = sg_datetime.now().date()
    #     underage_dob = today.replace(year=today.year - 10)  # 10 years old
    #     input_data = {
    #         "session_id": "test_session_id",
    #         "name": "Test User",
    #         "date_of_birth": underage_dob,
    #         "nationality": "Singapore Citizen",
    #         "language": "English",
    #         "gender": "Male"
    #     }
    #     print("Hello")
    #     with self.assertRaises(ValidationError):
    #         try:
    #             RegisterInput(**input_data)
    #         except Exception as e:
    #             print(f"Error {e}")    

if __name__ == '__main__':
    unittest.main()