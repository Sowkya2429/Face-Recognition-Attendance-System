import os
import pickle
import numpy as np
import cv2
import face_recognition
import cvzone
import firebase_admin
from firebase_admin import credentials, db, storage
import numpy as np
from datetime import datetime

# Initialize Firebase Admin SDK
cred = credentials.Certificate("FaceRecognition.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://attendanceusingfacerecog-default-rtdb.firebaseio.com/",
    'storageBucket': "attendanceusingfacerecog.appspot.com"
})

storage_bucket = storage.bucket()

# Capture video from webcam
video_capture = cv2.VideoCapture(0)
video_capture.set(3, 640)
video_capture.set(4, 480)

# Load background image
background_image = cv2.imread('Resources/background.png')

# Load mode images into a list
modes_folder_path = 'Resources/Modes'
mode_path_list = os.listdir(modes_folder_path)
mode_images_list = [cv2.imread(os.path.join(modes_folder_path, path)) for path in mode_path_list]

# Load encoding file
print("Loading File ...")
with open('EncodeFile.p', 'rb') as file:
    known_encodings_with_ids = pickle.load(file)
known_encodings, student_ids = known_encodings_with_ids
print("Encode File Loaded")

current_mode = 0
counter = 0
student_id = -1
student_image = []

while True:
    success, frame = video_capture.read()

    resized_frame = cv2.resize(frame, (0, 0), None, 0.25, 0.25)
    resized_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)

    current_face_locations = face_recognition.face_locations(resized_frame)
    current_face_encodings = face_recognition.face_encodings(resized_frame, current_face_locations)

    background_image[162:162 + 480, 55:55 + 640] = frame
    background_image[44:44 + 633, 808:808 + 414] = mode_images_list[current_mode]

    if current_face_locations:
        for encoding, face_location in zip(current_face_encodings, current_face_locations):
            matches = face_recognition.compare_faces(known_encodings, encoding)
            face_distances = face_recognition.face_distance(known_encodings, encoding)

            match_index = np.argmin(face_distances)

            if matches[match_index]:
                y1, x2, y2, x1 = [coord * 4 for coord in face_location]
                bbox = 55 + x1, 162 + y1, x2 - x1, y2 - y1
                background_image = cvzone.cornerRect(background_image, bbox, rt=0)
                student_id = student_ids[match_index]
                if counter == 0:
                    cvzone.putTextRect(background_image, "Loading", (275, 400))
                    cv2.imshow("Face Attendance", background_image)
                    cv2.waitKey(1)
                    counter = 1
                    current_mode = 1

        if counter != 0:
            if counter == 1:
                # Get student information from the database
                student_info = db.reference(f'Students/{student_id}').get()
                print(student_info)
                # Get the student image from the storage
                blob = storage_bucket.get_blob(f'Images/{student_id}.png')
                array = np.frombuffer(blob.download_as_string(), np.uint8)
                student_image = cv2.imdecode(array, cv2.COLOR_BGRA2BGR)
                # Update attendance data
                last_attendance_time = datetime.strptime(student_info['last_attendance_time'], "%Y-%m-%d %H:%M:%S")
                seconds_elapsed = (datetime.now() - last_attendance_time).total_seconds()
                print(seconds_elapsed)
                if seconds_elapsed > 30:
                    ref = db.reference(f'Students/{student_id}')
                    student_info['total_attendance'] += 1
                    ref.update({'total_attendance': student_info['total_attendance'],
                                'last_attendance_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                else:
                    current_mode = 3
                    counter = 0
                    background_image[44:44 + 633, 808:808 + 414] = mode_images_list[current_mode]

            if current_mode != 3:
                if 10 < counter < 20:
                    current_mode = 2

                background_image[44:44 + 633, 808:808 + 414] = mode_images_list[current_mode]

                if counter <= 10:
                    cv2.putText(background_image, str(student_info['total_attendance']), (861, 125),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 1)
                    cv2.putText(background_image, str(student_info['major']), (1006, 550),
                                cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(background_image, str(student_id), (1006, 493),
                                cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(background_image, str(student_info['standing']), (910, 625),
                                cv2.FONT_HERSHEY_COMPLEX, 0.6, (100, 100, 100), 1)
                    cv2.putText(background_image, str(student_info['year']), (1025, 625),
                                cv2.FONT_HERSHEY_COMPLEX, 0.6, (100, 100, 100), 1)
                    cv2.putText(background_image, str(student_info['starting_year']), (1125, 625),
                                cv2.FONT_HERSHEY_COMPLEX, 0.6, (100, 100, 100), 1)

                    (w, h), _ = cv2.getTextSize(student_info['name'], cv2.FONT_HERSHEY_COMPLEX, 1, 1)
                    offset = (414 - w) // 2
                    cv2.putText(background_image, str(student_info['name']), (808 + offset, 445),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (50, 50, 50), 1)

                    background_image[175:175 + 216, 909:909 + 216] = student_image

                counter += 1

                if counter >= 20:
                    counter = 0
                    current_mode = 0
                    student_info = []
                    student_image = []
                    background_image[44:44 + 633, 808:808 + 414] = mode_images_list[current_mode]
    else:
        current_mode = 0
        counter = 0

    cv2.imshow("Face Attendance", background_image)
    cv2.waitKey(1)
