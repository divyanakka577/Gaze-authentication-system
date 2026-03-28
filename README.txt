Gaze-Based Authentication System
This project implements a gaze-based authentication system using facial recognition, gaze tracking, and a maze-based user interaction. It combines modern technologies to enhance user authentication security.

Features

•Login System:

 •Users can log in using their username and password.
 •Facial recognition ensures the user's identity matches stored credentials.

•Gaze Tracking:

 •Users follow a maze path using their gaze.
 •Authentication is granted based on successful gaze-path tracking.

•Responsive Web Design:

 •Intuitive and user-friendly web interfaces for login, gaze authentication, and success pages.

•Security:

 •Passwords stored securely (ensure to use hashing in production).
 •Gaze-based authentication adds an extra layer of security.

•Technologies Used
 •Backend:

  •Python
  •Flask Framework

 •Frontend:

  •HTML5
  •CSS3 (Responsive Design)
  •JavaScript

 •Gaze Tracking:

  •GazeTracking Library
  •OpenCV for webcam access

 •Database:

  •MySQL
 •Other Tools:

  •Face Recognition Library

Setup Instructions
Prerequisites
•Python 3.7 or higher
•MySQL Database
•Web browser
•Webcam

Installation Steps
 1. Clone the Repository
 2. Install Dependencies:
    •pip install -r requirements.txt

 3. Set Up the Database:
    •Create a MySQL database (e.g., user_auth).
    •Import the schema:
      CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    face_data BLOB NOT NULL
     );

    •Insert sample user credentials and face data.
 4. Run the Application:
    •python app.py
 5. Access the Application:
    •Open your browser and go to: http://127.0.0.1:5000


Project Structure
.
├── app.py                 # Flask application logic
├── gaze_tracking_module.py # Gaze tracking and maze generation
├── templates/             # HTML templates
│   ├── login.html
│   ├── gaze_auth.html
│   └── success.html
├── static/                # CSS, JavaScript, and other assets
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation

Usage Instructions
 1. Login:
    •Enter the username and password.
    •Ensure your face is visible to the webcam for facial recognition.
 2. Gaze Authentication:
    •Follow the maze path with your gaze.
    •Click "Finish" when done.
 3. Authentication Outcome:
    •Success: Redirected to the success page.
    •Failure: Redirected to the login page to retry.

Customization
•Threshold Adjustment:
 •Modify the proximity threshold in gaze_tracking_module.py for more or less lenient gaze       matching.
•Maze Complexity:
 •Adjust the maze size in create_connected_maze_with_display(size=5) to generate simpler or more complex mazes.
•Styling:
 •Update CSS files in the static/ directory to customize the UI.

Known Issues
•Ensure proper lighting for accurate gaze and facial recognition.
•Webcam access may fail if permissions are not granted.


Future Enhancements
•Multi-user support with real-time session management.
•Integration with additional authentication factors.
•Deployment on a production server with HTTPS.


Acknowledgments
•GazeTracking Library
•OpenCV
•Flask

Enjoy using the Gaze-Based Authentication System! 🚀