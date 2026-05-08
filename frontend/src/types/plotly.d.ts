/// <reference types="plotly.js" />
/// <reference types="react" />

declare module 'react-plotly.js' {
  import { Component } from 'react';
  import type { Data, Layout, Config, Frame } from 'plotly.js';

  export interface PlotParams {
    data: Data[];
    layout?: Partial<Layout>;
    frames?: Partial<Frame>[];
    config?: Partial<Config>;
    onClick?: (event: any) => void;
    onHover?: (event: any) => void;
    onUnhover?: (event: any) => void;
    onSelected?: (event: any) => void;
    onDeselect?: (event: any) => void;
    onDoubleClick?: (event: any) => void;
    onInitialized?: (figure: any, graphDiv: any) => void;
    onUpdate?: (figure: any, graphDiv: any) => void;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    debug?: boolean;
    divId?: string;
  }

  export default class Plot extends Component<PlotParams> {}
} 