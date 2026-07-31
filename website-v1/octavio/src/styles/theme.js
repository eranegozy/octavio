// theme.js
import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  typography: {
    fontFamily: '"Jost", "Inter", "Helvetica", "Arial", sans-serif',
    h1: {
        fontSize: "2em",
        fontWeight: "bold"
    },
    h3: {
        fontSize: "1.25em"
    }
  },
});

export default theme;
