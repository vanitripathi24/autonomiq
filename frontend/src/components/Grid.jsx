import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, themeQuartz } from 'ag-grid-community'

ModuleRegistry.registerModules([AllCommunityModule])

const theme = themeQuartz.withParams({
  fontFamily: 'Schibsted Grotesk, system-ui, sans-serif', fontSize: 13.5, accentColor: '#0b3d91',
  foregroundColor: '#101b33', backgroundColor: '#ffffff', headerBackgroundColor: '#f4f6fb',
  headerTextColor: '#5b6784', borderColor: '#d8dee9', rowHoverColor: '#f0f4fb', wrapperBorderRadius: 10,
})

export default function Grid({ rows, cols, height = 360, ...rest }) {
  return (
    <div style={{ height }}>
      <AgGridReact theme={theme} rowData={rows} columnDefs={cols} animateRows
        defaultColDef={{ sortable: true, resizable: true, flex: 1, minWidth: 100 }} {...rest} />
    </div>
  )
}
