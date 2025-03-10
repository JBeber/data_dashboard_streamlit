import os
import streamlit as st
from streamlit_calendar import calendar

st.set_page_config(page_title="VV Events Calendar", 
                   page_icon="📆", 
                   layout="wide")

st.markdown(
    "# VV Events Calendar"
)

mode = st.selectbox(
    "Calendar Mode:",
    (
        "Month",
        "Week",
        "Day",
        "List",
    ),
)

def save_new_event(name, st_date, en_date, st_time, en_time):
    
    if event_start_time is not None:
        pass

    

    # calendar_events.append(
    #     {
    #     "title": event.event_name,
    #     "color": "#FF6C6C",
    #     "start": ,
    #     "end": ,

    #     },
    # )
    
new_event = st.popover('Add Event')
event_name = new_event.text_input('Event Name')

event_start_date = new_event.date_input("Start Date")
event_end_date = new_event.date_input("End Date")

if event_start_date == event_end_date:
    allday_event = new_event.checkbox('All day event?')
else:
    allday_event = True

if not allday_event:
    event_start_time = new_event.time_input('Start Time')
    event_end_time = new_event.time_input('End Time')
else:
    event_start_time = event_end_time = None

new_event.button('Save', on_click=save_new_event, args=(event_name,event_start_date,event_end_date,
                                                        event_start_time,event_end_time)
)

# Resources (e.g. specific rooms, equipment, or personnel
# are not needed at this time, but can be specified later
# should the need arise.
#  
# calendar_resources = [
#     {"id": "a", "building": "Building A", "title": "Room A"},
#     {"id": "b", "building": "Building A", "title": "Room B"},
#     {"id": "c", "building": "Building B", "title": "Room C"},
#     {"id": "d", "building": "Building B", "title": "Room D"},
#     {"id": "e", "building": "Building C", "title": "Room E"},
#     {"id": "f", "building": "Building C", "title": "Room F"},
# ]

calendar_options = {
    "editable": "true",
    "navLinks": "true",
    "selectable": "true",
    "height": 750
}

if mode == "Month":
    calendar_options = {
        **calendar_options,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "",
        },
        # "initialDate": "today"; defaults to today's date when not specified
        "initialView": "dayGridMonth",
    }
elif mode == "Week":
    calendar_options = {
        **calendar_options,
        "initialView": "timeGridWeek",
    }
elif mode == "Day":
    calendar_options = {
        **calendar_options,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "",
        },
        # "initialDate": "2023-07-01",
        "initialView": "timelineDay",
    }
elif mode == "List":
    calendar_options = {
        **calendar_options,
        # "initialDate": "2023-07-01",
        "initialView": "listMonth",
    }

calendar_events = [
    {
        "title": "Event 1",
        "color": "#FF6C6C",
        "start": "2025-03-10",
        "end": "2025-03-13",
    },
    {
        "title": "Event 2",
        "color": "#FFBD45",
        "start": "2025-03-01",
        "end": "2025-03-03",
    },
    {
        "title": "Event 3",
        "color": "#FF4B4B",
        "start": "2025-03-20",
        "end": "2025-03-20",
    },
    {
        "title": "Event 7",
        "color": "#FF4B4B",
        "start": "2025-03-20T08:30:00",
        "end": "2025-03-20T10:30:00",
    },
    {
        "title": "Event 17",
        "color": "#FFBD45",
        "start": "2025-03-13T15:30:00",
        "end": "2025-03-13T16:30:00",
    },
]

state = calendar(
    events=st.session_state.get("events", calendar_events),
    options=calendar_options,
    custom_css="""
    .fc-event-past {
        opacity: 0.8;
    }
    .fc-event-time {
        font-style: italic;
    }
    .fc-event-title {
        font-weight: 700;
    }
    .fc-toolbar-title {
        font-size: 2rem;
    }
    """,
    key=mode,
)

if state.get("eventsSet") is not None:
    st.session_state["events"] = state["eventsSet"]

# st.write(state)

# st.markdown("## API reference")
# st.help(calendar)