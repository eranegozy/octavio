import React, { useState, useEffect } from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval } from 'date-fns';
import "./DateSelector.css";

const DateSelector = ({notificationDates}: {notificationDates: Array<Date>}) => {
  const [startDate, setStartDate] = useState(new Date());
  const [baseMonth, setBaseMonth] = useState(new Date());
  const [allVisibleDays, setAllVisibleDays] = useState([]);


  const hasNotification = (date) => {
    const dateString = date.toISOString().split("T")[0];
    return notificationDates.includes(dateString);
  };

  const renderDay = (day, date) => {
    const showDot = date && hasNotification(date);
    return (
      <div className="custom-day-cell">
        <span>{day}</span>
        {showDot && <span className="notification-dot" />}
      </div>
    );
  };

  useEffect(() => {
    // Find the strict boundaries of the current active month
    const monthStart = startOfMonth(baseMonth);
    const monthEnd = endOfMonth(baseMonth);

    // Include the full visible calendar week grid rows
    const gridStart = startOfWeek(monthStart, { weekStartsOn: 0 }); // 0 = Sunday
    const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 0 });

    const daysGrid = eachDayOfInterval({ start: gridStart, end: gridEnd });
    console.log("here")
    setAllVisibleDays(daysGrid);
    console.log("All calendar grid days:", daysGrid);
  }, [baseMonth]);

  return (<>
    <DatePicker
        // selected={startDate}
        onChange={(date) => setStartDate(date)}
        // onMonthChange={(date) => setBaseMonth(date)}
        onMonthChange={(date) => setBaseMonth(date)}
        renderDayContents={renderDay}
        inline
    />
    </>
  );
}

export default DateSelector;