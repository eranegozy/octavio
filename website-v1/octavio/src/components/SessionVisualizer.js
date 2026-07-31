import { useEffect, useRef, useState } from "react";
import { Player, PianoRollSVGVisualizer, midiToSequenceProto } from '@magenta/music';

import * as React from 'react';
import { styled } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Slider from '@mui/material/Slider';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import PauseRounded from '@mui/icons-material/PauseRounded';
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded';
// import PlayerCanvas from '@/components/PlayerCanvas';
import * as Tone from 'tone';
// import PlaybackSlider from "@/components/PlaybackSlider";

const Widget = styled('div')(({ theme }) => ({
  padding: 16,
  borderRadius: 16,
  // width: 343,
  maxWidth: '100%',
  margin: 'auto',
  position: 'relative',
  zIndex: 1,
  backgroundColor: 'rgba(128,128,128,0.05)',
  backdropFilter: 'blur(40px)',
  ...theme.applyStyles('dark', {
    backgroundColor: 'rgba(0,0,0,0.6)',
  }),
}));

const TinyText = styled(Typography)({
  fontSize: '0.75rem',
  opacity: 0.38,
  fontWeight: 500,
  letterSpacing: 0.2,
});

export default function SessionVisualizer({ session }) {

    const session_id = session.session_id;
    const instrument_id = session.instrument_id;

    const [ midiSequence, setMidiSequence ] = useState(null);
    const svgRef = useRef(null);
    const [player, setPlayer] = useState(null);
    const [visualizer, setVisualizer] = useState(null);
    const animationRef = useRef(null);
    const scrollRef = useRef(null);

    useEffect(() => {
        fetch(`http://octavio-server.mit.edu:5001/api/midi?session_id=${session_id}&instrument_id=${instrument_id}`)
            .then(res => res.arrayBuffer())
            .then(arrayBuffer => setMidiSequence(midiToSequenceProto(arrayBuffer)))
    }, []);

    useEffect(() => {
        if (!midiSequence || !svgRef.current) return;

        // Create visualizer
        const vis = new PianoRollSVGVisualizer(
            midiSequence,
            svgRef.current,
            {
                noteHeight: 6,
                pixelsPerTimeStep: 60,
            });
        setVisualizer(vis);

        // Create player with run callback to update visualizer
        const newPlayer = new Player(false, {
            run: (note) => {
                vis.redraw(note);
                // setPosition(note.startTime);
                const scrollEl = scrollRef.current;
                const scrollPos = note.startTime * 60; // same as pixelsPerTimeStep
                scrollEl.scrollLeft = scrollPos - 100; // keep some margin
            },
            stop: () => {
                // console.log('Playback finished');
                setPlayingState('finished');
            },
        });
        setPlayer(newPlayer);
    }, [midiSequence]);

    const [isSeeking, setIsSeeking] = useState(false);

    useEffect(() => {
        if (!player) return;

        const tick = () => {
          // console.log(isSeeking);

          if (!isSeeking && player.isPlaying()) {
            const pos = Tone.Transport.seconds
            setPosition(pos);
            // console.log("pos set by animation", pos);
          }
          animationRef.current = requestAnimationFrame(tick);
        };

        animationRef.current = requestAnimationFrame(tick);

        return () => {
          if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
          }
        };
    }, [player, isSeeking]);

    useEffect(() => {
      return () => {
        if (!!player && player.isPlaying()) {
          player.stop();
        }
        // Optional: Tone.Transport.stop(); if you want to fully halt transport
      };
    }, [player]);


    const handlePlay = () => {
        if (player && midiSequence) {
            // if (playingState === 'finished') {
            //     setPosition(0);
            // }
            // else {
            //     player.start(midiSequence);
            // }
            player.start(midiSequence);
        }
    };

    const handlePause = () => {
        if (player && midiSequence) {
            player.pause(midiSequence);
        }
    };

    const handleResume = () => {
        if (player && midiSequence) {
            player.resume(midiSequence);
        }
    };

    // const handleSeek = (_, value) => {
    //     // setPlaybackTime(value);
    //     if (player && midiSequence && playingState != 'stopped' && playingState != 'finished') {
    //       setPosition(value);
    //       player.seekTo(value);
    //       visualizer.redraw(null);
    //     }
    //   };
    // const handleSeek = (_, value) => {
    //   // setPlaybackTime(value);
    //   if (player && midiSequence && playingState != 'stopped' && playingState != 'finished') {
    //     // setPosition(value);
    //     player.seekTo(value);
    //     visualizer.redraw(null);
    //   }
    // };

    function updatePlayerPosition() {
      if (!player.isPlaying()) {
        player.start(midiSequence);
        player.pause(midiSequence);
        setPlayingState('paused');
      }

      player.seekTo(position);
      visualizer.redraw(null);
    }

    const duration = !midiSequence ? 0 : midiSequence.totalTime;

    // console.log(!midiSequence ? 'Nope' : midiSequence.totalTime)






    // const duration = 200; // seconds
    const [position, setPosition] = React.useState(0);
    // console.log("position", position);
    // const [paused, setPaused] = React.useState(true);
    const [playingState, setPlayingState] = React.useState('stopped');
    function formatDuration(value) {
        const minute = Math.floor(value / 60);
        const secondLeft = Math.floor(value - minute * 60);
        // const secondLeft = value - minute * 60;
        return `${minute}:${secondLeft < 10 ? `0${secondLeft}` : secondLeft}`;
    }

    const sliderSx = {
        color: 'rgba(0,0,0,0.87)',
        height: 4,
      };

    // const sliderRef = useRef(null);

    // useEffect(() => {
    //     if (sliderRef.current) {
    //       // Manually set the slider's input value
    //       const input = sliderRef.current.querySelector('input[type="range"]');
    //       if (input) {
    //         input.value = position;
    //         input.dispatchEvent(new Event('input', { bubbles: true }));
    //       }
    //     }
    //   }, [position]);


    // const sliderRef = useRef();

    // useEffect(() => {
    //   if (sliderRef.current) {
    //     const input = sliderRef.current.querySelector('input[type="range"]');
    //     if (input) {
    //       input.value = position;
    //       input.dispatchEvent(new Event('input', { bubbles: true }));
    //     }
    //   }
    // }, [position]);

  return (
    <Box sx={{ width: '100%', overflow: 'hidden', position: 'relative', p: 3 }}>
      <Widget sx={{ width: '100%', height: '100%' }}>
      {/* <Box sx={{ width: '100%', height: '100%', backgroundColor: 'rgba(128,128,128,0.05)', padding: 4, borderRadius: 16 }}> */}
        <Box
          ref={scrollRef}
          sx={{
            width: '100%',
            height: '100%',
            overflowX: 'auto',
            overflowY: 'hidden',
            scrollbarWidth: 'none', // Firefox
            msOverflowStyle: 'none', // IE/Edge
            '&::-webkit-scrollbar': { display: 'none'}
          }}>
            <svg ref={svgRef} width='80%' height='90%' />
        </Box>

        {/* <PlaybackSlider duration={duration} position={position}></PlaybackSlider> */}

        {/* <Slider
          // key={Math.floor(position * 100)}
          ref={sliderRef}
          aria-label="time-indicator"
          size="small"
          value={position}
          min={0}
          max={duration}
          step={1}
          // onChange={(_, value) => {
          //   setIsSeeking(true);
          //   // setPosition(value);
          // }}
          // onChangeCommitted={(_, value) => {
          //   handleSeek(undefined, value)
          //   setIsSeeking(false);
          //   // player.seekToPosition(value);
          // }}
          sx={sliderSx}
        /> */}
        <Stack direction='row' justifyContent='space-around' alignItems='center'>
          <TinyText>{formatDuration(position)}</TinyText>
          <Box
            component="input"
            type="range"
            value={position}
            // readOnly
            onMouseDown={
              (_) => {setIsSeeking(true)}
              // (e) => setPosition(Number(e.target.value))
            }
            onChange={
              (e) => {setPosition(Number(e.target.value))}
              // (e) => setPosition(Number(e.target.value))
            }
            onMouseUp={
              (_) => {updatePlayerPosition(); setIsSeeking(false)}
            }
            min={0}
            max={duration}
            step={0.01}

            sx={{
              width: "90%",
              accentColor: "#9f46da",
              cursor: "pointer",
              // '&::-webkit-slider-runnable-track': {
              //   background: "white",
              //   borderRadius: 2
              // },
              // '&::-moz-range-track': {
              //   background: "white"
              // },
              // '&::-ms-track': {
              //   background: "white"
              // }
            }}

            // sx={{
            //   width: '90%',
            //   WebkitAppearance: 'none',
            //   height: 4,
            //   borderRadius: 2,
            //   // background: 'transparent',
            //   outline: 'none',
            //   cursor: 'pointer',

            //   // Dynamic progress styling using background gradient
            //   // backgroundImage: `linear-gradient(to right, #9f46da ${(position / duration) * 100}%, white ${(position / duration) * 100}%)`,

            //   '&:hover': {
            //     opacity: 1,
            //   },

            //   // Thumb styling
              // '&::-webkit-slider-thumb': {
              //   WebkitAppearance: 'none',
              //   height: 14,
              //   width: 14,
              //   borderRadius: '50%',
              //   background: '#9f46da',
              //   cursor: 'pointer',
              //   marginTop: '-5px',
              //   boxShadow: '0 2px 4px rgba(0,0,0,0.4)',
              //   transition: 'background 0.2s',
              // },
            //   '&::-moz-range-thumb': {
            //     height: 14,
            //     width: 14,
            //     borderRadius: '50%',
            //     background: '#9f46da',
            //     cursor: 'pointer',
            //     boxShadow: '0 2px 4px rgba(0,0,0,0.4)',
            //   },
            //   '&::-ms-thumb': {
            //     height: 14,
            //     width: 14,
            //     borderRadius: '50%',
            //     background: '#9f46da',
            //     cursor: 'pointer',
            //   },

            //   // Track fallback for older browsers
            //   '&::-webkit-slider-runnable-track': {
            //     height: 4,
            //     borderRadius: 2,
            //     background: 'transparent',
            //   },
            //   '&::-moz-range-track': {
            //     height: 4,
            //     borderRadius: 2,
            //     background: 'white',
            //   },
            //   '&::-ms-track': {
            //     height: 4,
            //     borderRadius: 2,
            //     background: 'transparent',
            //     borderColor: 'transparent',
            //     color: 'transparent',
            //   },
            // }}
          />
          <TinyText>{formatDuration(duration)}</TinyText>
        </Stack>


        {/* <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mt: -2,
          }}
        >
          <TinyText>{formatDuration(position)}</TinyText>
          <TinyText>{formatDuration(duration)}</TinyText>
        </Box> */}
        <Box
          sx={(theme) => ({
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mt: -1,
            '& svg': {
              color: '#000',
              ...theme.applyStyles('dark', {
                color: '#fff',
              }),
            },
          })}
        >
          <IconButton
            aria-label={playingState == 'playing' ? 'pause' : 'play'}
            onClick={() => {
                if (playingState === 'stopped') {
                    handlePlay();
                    setPlayingState('playing');
                }
                else if (playingState === 'paused') {
                    handleResume();
                    setPlayingState('playing');
                }
                else if (playingState === 'playing') {
                    handlePause();
                    setPlayingState('paused');
                }
                else if (playingState === 'finished') {
                    handlePlay();
                    setPlayingState('playing');
                }
            }}
          >
            {playingState === 'playing' ? (
              <PauseRounded sx={{ fontSize: '3rem' }} />
            ) : (
              <PlayArrowRounded sx={{ fontSize: '3rem' }} />
            )}
          </IconButton>
          {/* <Typography>{position}</Typography> */}
        </Box>
      </Widget>
      {/* </Box> */}
    </Box>
  );
}
