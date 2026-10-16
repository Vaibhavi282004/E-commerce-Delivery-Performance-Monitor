Attribute VB_Name = "WeeklyReport"
Option Explicit
'------------------------------------------------------------------------------
' WeeklyReport.bas
' Builds a formatted weekly summary workbook from the CSV files the Python
' pipeline writes to data/processed/.
'
' HOW TO USE
'   1. Run the pipeline:  python -m src.run_pipeline --raw-dir data/raw
'   2. Open Excel, press Alt+F11, choose File > Import File..., pick this .bas
'   3. Press Alt+F8, select BuildWeeklyReport, click Run
'   4. Choose the data/processed folder when asked
'
' STATUS: written carefully but NOT run in Excel by the author (the build
' environment had no Excel). Test it on the sample data first and fix any
' small issues you hit. Debugging it is good interview material.
'
' Numbers use your Windows regional settings. If decimals look wrong, check that
' the CSV decimal separator is a dot and your Excel list separator is a comma.
'------------------------------------------------------------------------------

Private Const TOP_N_SELLERS As Long = 25

Public Sub BuildWeeklyReport()
    Dim folder As String
    folder = PickFolder()
    If folder = "" Then Exit Sub

    Dim wbOut As Workbook
    Set wbOut = Workbooks.Add
    Application.ScreenUpdating = False

    On Error GoTo Fail

    Dim wsKpi As Worksheet, wsSellers As Worksheet, wsState As Worksheet
    Set wsKpi = wbOut.Worksheets(1)
    wsKpi.Name = "KPI Summary"
    Set wsSellers = wbOut.Worksheets.Add(After:=wbOut.Worksheets(wbOut.Worksheets.Count))
    wsSellers.Name = "Seller Scorecard"
    Set wsState = wbOut.Worksheets.Add(After:=wbOut.Worksheets(wbOut.Worksheets.Count))
    wsState.Name = "Delivery by State"

    ImportCsv wsKpi, folder & "kpi_summary.csv"
    ImportCsv wsSellers, folder & "seller_scorecard.csv"
    ImportCsv wsState, folder & "delivery_by_state.csv"

    FormatKpi wsKpi
    FormatSellers wsSellers
    FormatState wsState

    wsKpi.Activate
    Dim outPath As String
    outPath = folder & "Weekly_Report_" & Format(Date, "yyyymmdd") & ".xlsx"
    Application.DisplayAlerts = False
    wbOut.SaveAs Filename:=outPath, FileFormat:=xlOpenXMLWorkbook
    Application.DisplayAlerts = True
    Application.ScreenUpdating = True
    MsgBox "Report saved to:" & vbCrLf & outPath, vbInformation, "Weekly report"
    Exit Sub

Fail:
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    MsgBox "Could not build the report: " & Err.Description & vbCrLf & _
           "Check that the pipeline has been run and the CSV files exist.", vbExclamation
End Sub

'--- helpers ------------------------------------------------------------------

Private Function PickFolder() As String
    With Application.FileDialog(msoFileDialogFolderPicker)
        .Title = "Select the data/processed folder"
        If .Show = -1 Then
            PickFolder = .SelectedItems(1)
            If Right$(PickFolder, 1) <> Application.PathSeparator Then
                PickFolder = PickFolder & Application.PathSeparator
            End If
        End If
    End With
End Function

Private Sub ImportCsv(ws As Worksheet, path As String)
    If Dir(path) = "" Then Err.Raise vbObjectError + 1, , "File not found: " & path
    Dim src As Workbook
    Set src = Workbooks.Open(Filename:=path, ReadOnly:=True)
    src.Worksheets(1).UsedRange.Copy Destination:=ws.Range("A1")
    src.Close SaveChanges:=False
End Sub

Private Sub StyleHeader(ws As Worksheet)
    With ws.Range(ws.Cells(1, 1), ws.Cells(1, ws.UsedRange.Columns.Count))
        .Font.Bold = True
        .Font.Color = RGB(255, 255, 255)
        .Interior.Color = RGB(31, 56, 100)
    End With
    ws.Rows(1).RowHeight = 22
End Sub

Private Function ColumnOf(ws As Worksheet, header As String) As Long
    Dim c As Long
    For c = 1 To ws.UsedRange.Columns.Count
        If LCase$(CStr(ws.Cells(1, c).Value)) = LCase$(header) Then
            ColumnOf = c
            Exit Function
        End If
    Next c
End Function

Private Sub FormatKpi(ws As Worksheet)
    StyleHeader ws
    ws.Columns("A:B").AutoFit
    ws.Range("A1").EntireColumn.ColumnWidth = 28
    Dim lastRow As Long: lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    ws.Range("B2:B" & lastRow).NumberFormat = "#,##0.00"
    ws.Range("A1:B" & lastRow).Borders.LineStyle = xlContinuous
    ws.Range("A1:B" & lastRow).Borders.Color = RGB(200, 200, 200)
End Sub

Private Sub FormatSellers(ws As Worksheet)
    Dim lastRow As Long: lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    Dim cLate As Long: cLate = ColumnOf(ws, "late_pct")
    Dim cTier As Long: cTier = ColumnOf(ws, "tier")

    ' keep only the worst TOP_N_SELLERS rows (file is already sorted by late_pct desc)
    If lastRow > TOP_N_SELLERS + 1 Then
        ws.Rows(TOP_N_SELLERS + 2 & ":" & lastRow).Delete
        lastRow = TOP_N_SELLERS + 1
    End If

    StyleHeader ws
    ws.Columns.AutoFit

    If cLate > 0 Then
        With ws.Range(ws.Cells(2, cLate), ws.Cells(lastRow, cLate)).FormatConditions.AddColorScale(ColorScaleType:=3)
            .ColorScaleCriteria(1).FormatColor.Color = RGB(99, 190, 123)
            .ColorScaleCriteria(2).FormatColor.Color = RGB(255, 235, 132)
            .ColorScaleCriteria(3).FormatColor.Color = RGB(248, 105, 107)
        End With
    End If

    If cTier > 0 Then
        Dim r As Long
        For r = 2 To lastRow
            Select Case ws.Cells(r, cTier).Value
                Case "Red":   ws.Cells(r, cTier).Interior.Color = RGB(248, 105, 107)
                Case "Amber": ws.Cells(r, cTier).Interior.Color = RGB(255, 217, 102)
                Case "Green": ws.Cells(r, cTier).Interior.Color = RGB(169, 208, 142)
            End Select
        Next r
    End If

    ws.Range("A2").Select
    ActiveWindow.FreezePanes = True
End Sub

Private Sub FormatState(ws As Worksheet)
    StyleHeader ws
    ws.Columns.AutoFit
    Dim lastRow As Long: lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    Dim cLate As Long: cLate = ColumnOf(ws, "late_pct")
    If cLate > 0 Then
        With ws.Range(ws.Cells(2, cLate), ws.Cells(lastRow, cLate)).FormatConditions.AddDatabar
            .BarColor.Color = RGB(248, 105, 107)
        End With
    End If
End Sub
