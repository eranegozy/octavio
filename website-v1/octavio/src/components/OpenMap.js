'use client';

import { Map, Marker, NavigationControl, Popup } from 'react-map-gl/maplibre';
import { LngLat, LngLatBounds } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import Box from "@mui/material/Box"
import MarkerPopup from './MarkerPopup';
import { useState, useEffect } from 'react';

export default function OpenMap() {
    const swPt = new LngLat(-71.104730, 42.353749);
    const nePt = new LngLat(-71.087138, 42.364879);
    const mitBounds = new LngLatBounds(swPt, nePt);

    // const center = new LngLat( (swPt.lng + nePt.lng) / 2, (swPt.lat + nePt.lat) / 2 );

    const [ instruments, setInstruments ] = useState(null);

    useEffect(() => {
        fetch('http://octavio-server.mit.edu:5001/api/instruments')
            .then(res => res.json())
            .then(data => setInstruments(data));
    }, []);

    const markerPopups = !!instruments ?
                            instruments.map(instrument => <MarkerPopup key={instrument.id} instrument={instrument}/>) :
                            [];

    return (
        <Map
            initialViewState={{
                bounds: mitBounds,
                // fitBoundsOptions: { padding: 20 }
            }}
            maxBounds={mitBounds}
            // zoom={12}
            // dragPan={false}
            mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" // OSM tiles
        >
            {/* <NavigationControl position="top-right" /> */}
            {/* <Marker longitude={center.lng} latitude={center.lat}>
                <div style={{ color: 'red', fontSize: '24px' }}>📍</div>
            </Marker>
            <Popup longitude={center.lng} latitude={center.lat}></Popup> */}
            {/* <MarkerPopup latitude={center.lat} longitude={center.lng} /> */}
            {markerPopups}
        </Map>
    );
}
