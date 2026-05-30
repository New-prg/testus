declare const _default: {
    content: string[];
    theme: {
        extend: {
            colors: {
                ink: string;
                canvas: string;
                panel: string;
                panelStrong: string;
                line: string;
                muted: string;
                cream: string;
                brass: string;
                ember: string;
                signal: string;
                success: string;
                warning: string;
                danger: string;
            };
            fontFamily: {
                display: [string, string, string];
                sans: [string, string, string];
            };
            boxShadow: {
                panel: string;
                glow: string;
            };
            borderRadius: {
                card: string;
                pill: string;
            };
            backgroundImage: {
                'cockpit-grid': string;
                'radar-glow': string;
                grain: string;
            };
            keyframes: {
                reveal: {
                    '0%': {
                        opacity: string;
                        transform: string;
                    };
                    '100%': {
                        opacity: string;
                        transform: string;
                    };
                };
                pulseLine: {
                    '0%, 100%': {
                        opacity: string;
                    };
                    '50%': {
                        opacity: string;
                    };
                };
            };
            animation: {
                reveal: string;
                'pulse-line': string;
            };
        };
    };
    plugins: never[];
};
export default _default;
