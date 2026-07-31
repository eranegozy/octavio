import { Slider } from "@mui/material";

export default function PlaybackSlider({ position, duration }) {
    return (
      <Slider
        value={position}
        min={0}
        max={duration}
        step={0.01}
        sx={{
          height: 4,
          color: 'rgba(0,0,0,0.87)',
        }}
      />
    );
  }
