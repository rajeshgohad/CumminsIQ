STATIONS = [
    {"id": 1,  "code": "STN-01", "name": "Cylinder Block Prep",   "target_ct": 180, "machine": "CNC Machining Center"},
    {"id": 2,  "code": "STN-02", "name": "Crankshaft Install",     "target_ct": 240, "machine": "Assembly Press"},
    {"id": 3,  "code": "STN-03", "name": "Piston & Con-Rod Assy",  "target_ct": 210, "machine": "Manual Assembly"},
    {"id": 4,  "code": "STN-04", "name": "Cylinder Head Torque",   "target_ct": 195, "machine": "Torque Station"},
    {"id": 5,  "code": "STN-05", "name": "Oil System & Sump",      "target_ct": 150, "machine": "Manual Assembly"},
    {"id": 6,  "code": "STN-06", "name": "Fuel Injection System",  "target_ct": 220, "machine": "Robotic Assembly"},
    {"id": 7,  "code": "STN-07", "name": "Turbocharger Mount",     "target_ct": 165, "machine": "Torque Station"},
    {"id": 8,  "code": "STN-08", "name": "Cooling System",         "target_ct": 180, "machine": "Manual Assembly"},
    {"id": 9,  "code": "STN-09", "name": "ECM & Electrical",       "target_ct": 200, "machine": "Electronic Assembly"},
    {"id": 10, "code": "STN-10", "name": "Intake & Exhaust",       "target_ct": 175, "machine": "Manual Assembly"},
    {"id": 11, "code": "STN-11", "name": "Final Torque & Check",   "target_ct": 240, "machine": "Torque Station"},
    {"id": 12, "code": "STN-12", "name": "Engine Test Cell",       "target_ct": 480, "machine": "Test Equipment"},
]

OPERATORS = {
    "A": ["J. Martinez","L. Chen","M. Johnson","S. Kim","R. Patel","A. Brown",
          "T. Davis","N. Wilson","C. Lee","M. Garcia","K. Thompson","D. Moore"],
    "B": ["B. Jackson","F. White","G. Harris","H. Martin","I. Taylor","J. Anderson",
          "K. Thomas","L. Walker","M. Hall","N. Allen","O. Young","P. King"],
    "C": ["Q. Scott","R. Green","S. Baker","T. Adams","U. Nelson","V. Carter",
          "W. Mitchell","X. Roberts","Y. Turner","Z. Phillips","A. Campbell","B. Parker"],
}

CURRENT_SHIFT = "B"
SHIFT_START = "14:00"
SHIFT_END = "22:00"
TARGET_PER_HOUR = 52
