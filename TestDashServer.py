import dash
from dash.dependencies import Output, Input, State
from dash import dcc, html
from datetime import datetime
import json
import plotly.graph_objs as go
from collections import deque
from flask import Flask, request
import pandas as pd  # Import pandas
import re
import os



# Initialize the Flask server
server = Flask(__name__)

# Initialize the Dash app
app = dash.Dash(__name__, server=server)

MAX_DATA_POINTS = 1000
UPDATE_FREQ_MS = 100

time = deque(maxlen=MAX_DATA_POINTS)
watchtime = deque(maxlen=MAX_DATA_POINTS)
accel_x = deque(maxlen=MAX_DATA_POINTS)
accel_y = deque(maxlen=MAX_DATA_POINTS)
accel_z = deque(maxlen=MAX_DATA_POINTS)

#wristmotion values
wrist_rotation_rate_x = deque(maxlen=MAX_DATA_POINTS)
wrist_rotation_rate_y = deque(maxlen=MAX_DATA_POINTS)
wrist_rotation_rate_z = deque(maxlen=MAX_DATA_POINTS)
wrist_gravity_x = deque(maxlen=MAX_DATA_POINTS)
wrist_gravity_y = deque(maxlen=MAX_DATA_POINTS)
wrist_gravity_z = deque(maxlen=MAX_DATA_POINTS)
wrist_acceleration_x = deque(maxlen=MAX_DATA_POINTS)
wrist_acceleration_y = deque(maxlen=MAX_DATA_POINTS)
wrist_acceleration_z = deque(maxlen=MAX_DATA_POINTS)
wrist_quaternion_w = deque(maxlen=MAX_DATA_POINTS)
wrist_quaternion_x = deque(maxlen=MAX_DATA_POINTS)
wrist_quaternion_y = deque(maxlen=MAX_DATA_POINTS)
wrist_quaternion_z = deque(maxlen=MAX_DATA_POINTS)



# Global variable to store recording state
recording_state = True #true for debugging, set to false when not recording
firstmsgRx = False

# Define the layout of the Dash app
app.layout = html.Div(children=[
    html.H1(children='Wear-axSpA Data Recorder'),
    html.Div([
        html.Label('Participant Number:'),
        dcc.Input(id='input-box', type='text'),
        html.Br(),  # New line added here
        html.Br(),
        html.Label('Select an option:'),
        dcc.RadioItems(
            id='radio-items',
            options=[
                {'label': 'BASMI', 'value': 'BASMI'},
                {'label': 'mBASMI', 'value': 'mBASMI'},
                {'label': 'ASPI', 'value': 'ASPI'}
            ],
            value='BASMI'  # Default value
        ),
    
        html.Br(),
        html.Button('Submit', id='submit-button'),
        html.Div(id='output-div1'),
        html.Br(),
        
        html.H2('Phone data:'),
        dcc.Graph(id="live_graph"),
        dcc.Interval(id="counter", interval=UPDATE_FREQ_MS),

        html.H2('Watch data:'),  # New section for watch data
        dcc.Graph(id="live_graph_watch"),
        #dcc.Interval(id="counter_watch", interval=UPDATE_FREQ_MS),

        html.Button("Start Recording", id="record_button", n_clicks=0),
        html.Button("Save Recording", id="save_button", n_clicks=0),
        dcc.Store(id="recording_state", data=False),
        html.Br(),
        html.Br(),
        html.Div(id='output-div2'),
    ])
])

@app.callback(
    Output('output-div1', 'children'),
    Input('submit-button', 'n_clicks'),
    Input('input-box', 'value')
)
def update_output(n_clicks, value):
    if n_clicks is not None:
        # Assign the input value to a variable
        input_value = value
        return f'You have entered: {input_value}'
    return 'Participant number not entered'

@app.callback(
    Output("recording_state", "data"),
    Output("record_button", "children"),
    Input("record_button", "n_clicks"),
    State("recording_state", "data")
)
def toggle_recording(n_clicks, state):
    global recording_state
    if n_clicks % 2 == 1:
        recording_state = True
        return True, "Stop Recording"
    else:
        recording_state = False
        return False, "Start Recording"

@app.callback(Output("live_graph", "figure"), Input("counter", "n_intervals"))
def update_graph(_counter):
    global recording_state
    if not recording_state:
        return dash.no_update
    data = [
        go.Scatter(x=list(time), y=list(d), name=name)
        for d, name in zip([accel_x, accel_y, accel_z], ["X", "Y", "Z"])
    ]

    graph = {
        "data": data,
        "layout": go.Layout(
            {
                "xaxis": {"type": "date"},
                "yaxis": {"title": "Acceleration ms<sup>-2</sup>"},
            }
        ),
    }
    if (
        len(time) > 0
    ):  #  cannot adjust plot ranges until there is at least one data point
        graph["layout"]["xaxis"]["range"] = [min(time), max(time)]
        graph["layout"]["yaxis"]["range"] = [
            min(min(accel_x), min(accel_y), min(accel_z)),
            max(max(accel_x), max(accel_y), max(accel_z)),
        ]

    return graph

@app.callback(Output("live_graph_watch", "figure"), Input("counter", "n_intervals"))
def update_watch_graph(_counter):
    global recording_state
    if not recording_state:
        return dash.no_update
    data = [
    go.Scatter(x=list(watchtime), y=list(d), name=name)
    for d, name in zip(
        [wrist_acceleration_x, wrist_acceleration_y, wrist_acceleration_z],
        ["Wrist X", "Wrist Y", "Wrist Z"]
        )
    ]

    graph = {
        "data": data,
        "layout": go.Layout(
            {
                "xaxis": {"type": "date"},
                "yaxis": {"title": "Wrist Acceleration ms<sup>-2</sup>"},
            }
        ),
    }
    if len(time) > 0:
        graph["layout"]["xaxis"]["range"] = [min(watchtime), max(watchtime)]
        graph["layout"]["yaxis"]["range"] = [
            min(min(wrist_acceleration_x), min(wrist_acceleration_y), min(wrist_acceleration_z)),
            max(max(wrist_acceleration_x), max(wrist_acceleration_y), max(wrist_acceleration_z)),
        ]

    return graph


@app.callback(
    Output('output-div2', 'children'),
    Input("save_button", "n_clicks"),
    State("recording_state", "data"),
    State("input-box", "value"),
    State("radio-items", "value")
)
def save_data(n_clicks, recording_state, participant_number, radio_selection):
    if n_clicks > 0 and not recording_state and participant_number:
        # Validate and sanitize inputs
        if not re.match("^[a-zA-Z0-9_-]{1,20}$", participant_number):
            # Handle invalid participant_number
            return 'Invalid participant number'
        if not re.match("^[a-zA-Z0-9_-]+$", radio_selection):
            return 'Invalid radio selection'

        df = pd.DataFrame({
            'time': list(time),
            'accel_x': list(accel_x),
            'accel_y': list(accel_y),
            'accel_z': list(accel_z)
        })
        
        # Generate a unique filename
        filename = f"{participant_number}_{radio_selection}_{datetime.now().strftime('%b%d_%H%Mhr')}.csv"
        if os.path.exists(filename):
            filename = f"{participant_number}_{radio_selection}_{datetime.now().strftime('%b%d_%H%Mhr')}_{uuid.uuid4().hex}.csv"
        
        df.to_csv(filename, index=False)
        return f'File saved as: {filename}'
    
    if not participant_number:
        return 'Participant number not entered'
    else:
        return 'File not saved'
    

@server.route("/data", methods=["POST"])
def data():  # listens to the data streamed from the sensor logger
    global recording_state, firstmsgRx
    if str(request.method) == "POST":
        try:
            data = json.loads(request.data)
        except json.JSONDecodeError:
            return "Invalid JSON data", 400
        data = json.loads(request.data)
        """ if not firstmsgRx:
            print("First message received")
            print(json.dumps(data, indent=4))
            firstmsgRx = True
            with open("first_message.txt", "w") as f:
                f.write(json.dumps(data, indent=4)) """
        # Print the entire JSON payload
        #print(json.dumps(data, indent=4))
        
        for d in data['payload']:
            #print('processing data:')
            #print(d.get("name", None))

            if (
                d.get("name", None) == "accelerometer"
            ):  #  modify to access different sensors
                ts = datetime.fromtimestamp(d["time"] / 1000000000)
                if len(time) == 0 or ts > time[-1]:
                    
                    # modify the following based on which sensor is accessed, log the raw json for guidance
                    if recording_state:  # Check recording state
                        time.append(ts)
                        accel_x.append(d["values"]["x"])
                        accel_y.append(d["values"]["y"])
                        accel_z.append(d["values"]["z"])
                        #print("Phone data received ✅")
            if d.get("name", None) == "wrist motion":
                #print("Wrist motion data received ✅")
                ts = datetime.fromtimestamp(d["time"] / 1000000000)
                if len(watchtime) == 0 or ts > watchtime[-1]:
                    #print("Here ❗")
                    if recording_state:
                        #print("Wrist motion data processing⏲️")
                        watchtime.append(ts)
                        wrist_rotation_rate_x.append(d["values"]["rotationRateX"])
                        wrist_rotation_rate_y.append(d["values"]["rotationRateY"])
                        wrist_rotation_rate_z.append(d["values"]["rotationRateZ"])
                        wrist_gravity_x.append(d["values"]["gravityX"])
                        wrist_gravity_y.append(d["values"]["gravityY"])
                        wrist_gravity_z.append(d["values"]["gravityZ"])
                        wrist_acceleration_x.append(d["values"]["accelerationX"])
                        wrist_acceleration_y.append(d["values"]["accelerationY"])
                        wrist_acceleration_z.append(d["values"]["accelerationZ"])
                        wrist_quaternion_w.append(d["values"]["quaternionW"])
                        wrist_quaternion_x.append(d["values"]["quaternionX"])
                        wrist_quaternion_y.append(d["values"]["quaternionY"])
                        wrist_quaternion_z.append(d["values"]["quaternionZ"])
                        #print("Wrist motion data received ✅")
    return "success", 200

# Run the server
if __name__ == '__main__':
    app.run_server(port=8000, host="0.0.0.0")