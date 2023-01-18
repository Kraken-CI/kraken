import { BrowserModule, Title } from '@angular/platform-browser'
import { BrowserAnimationsModule } from '@angular/platform-browser/animations'
import { NgModule } from '@angular/core'
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http'
import { ReactiveFormsModule, FormsModule } from '@angular/forms'

import { CodemirrorModule } from '@ctrl/ngx-codemirror'
import { CookieService } from 'ngx-cookie-service'

import { PanelMenuModule } from 'primeng/panelmenu'
import { MenuModule } from 'primeng/menu'
import { SplitButtonModule } from 'primeng/splitbutton'
import { DropdownModule } from 'primeng/dropdown'
import { MultiSelectModule } from 'primeng/multiselect'
import { TableModule } from 'primeng/table'
import { PanelModule } from 'primeng/panel'
import { TreeModule } from 'primeng/tree'
import { TreeTableModule } from 'primeng/treetable'
import { ToastModule } from 'primeng/toast'
import { MessageService } from 'primeng/api'
import { TabViewModule } from 'primeng/tabview'
import { OrganizationChartModule } from 'primeng/organizationchart'
import { ChartModule } from 'primeng/chart'
import { SelectButtonModule } from 'primeng/selectbutton'
import { DialogModule } from 'primeng/dialog'
import { InputTextModule } from 'primeng/inputtext'
import { InputTextareaModule } from 'primeng/inputtextarea'
import { MessageModule } from 'primeng/message'
import { MessagesModule } from 'primeng/messages'
import { ConfirmDialogModule } from 'primeng/confirmdialog'
import { ConfirmationService } from 'primeng/api'
import { InplaceModule } from 'primeng/inplace'
import { PaginatorModule } from 'primeng/paginator'
import { TabMenuModule } from 'primeng/tabmenu'
import { CheckboxModule } from 'primeng/checkbox'
import { MenubarModule } from 'primeng/menubar'
import { InputSwitchModule } from 'primeng/inputswitch'
import { InputNumberModule } from 'primeng/inputnumber'
import { PasswordModule } from 'primeng/password'
import { TooltipModule } from 'primeng/tooltip'
import { ToggleButtonModule } from 'primeng/togglebutton'
import { FieldsetModule } from 'primeng/fieldset'
import { RadioButtonModule } from 'primeng/radiobutton'
import { CardModule } from 'primeng/card'
import { SliderModule } from 'primeng/slider'
import { ProgressSpinnerModule } from 'primeng/progressspinner'
import { ListboxModule } from 'primeng/listbox'
import { DividerModule } from 'primeng/divider'
import { KeyFilterModule } from 'primeng/keyfilter'

// REST API
import {
    ApiModule,
    BASE_PATH,
    Configuration,
    ConfigurationParameters,
} from './backend'

import { AppRoutingModule } from './app-routing.module'
import { AppComponent } from './app.component'
import { AuthInterceptor } from './auth.interceptor'
import { LocaltimePipe } from './localtime.pipe'
import { BreadcrumbsService } from './breadcrumbs.service'

import { BranchResultsComponent } from './branch-results/branch-results.component'
import { RunResultsComponent } from './run-results/run-results.component'
import { BreadcrumbsComponent } from './breadcrumbs/breadcrumbs.component'
import { MainPageComponent } from './main-page/main-page.component'
import { TestCaseResultComponent } from './test-case-result/test-case-result.component'
import { BranchMgmtComponent } from './branch-mgmt/branch-mgmt.component'
import { RunBoxComponent } from './run-box/run-box.component'
import { NewFlowComponent } from './new-flow/new-flow.component'
import { NewRunComponent } from './new-run/new-run.component'
import { LogBoxComponent, NoSanitizePipe } from './log-box/log-box.component'
import { ProjectSettingsComponent } from './project-settings/project-settings.component'
import { AgentsPageComponent } from './agents-page/agents-page.component'
import { DiscoveredPageComponent } from './discovered-page/discovered-page.component'
import { GroupsPageComponent } from './groups-page/groups-page.component'
import { SettingsPageComponent } from './settings-page/settings-page.component'
import { DiagsPageComponent } from './diags-page/diags-page.component'
import { RepoChangesComponent } from './repo-changes/repo-changes.component'
import { GrpCloudCfgComponent } from './grp-cloud-cfg/grp-cloud-cfg.component'
import { TcrTableComponent } from './tcr-table/tcr-table.component'
import { FlowAnalysisComponent } from './flow-analysis/flow-analysis.component'
import {
    TabbedPageComponent,
    TabbedPageTabComponent,
} from './tabbed-page/tabbed-page.component'
import { FlowPageComponent } from './flow-page/flow-page.component'
import { FlowChartsComponent } from './flow-charts/flow-charts.component'
import { BranchStatsComponent } from './branch-stats/branch-stats.component'

export function cfgFactory() {
    const params: ConfigurationParameters = {
        apiKeys: {},
        withCredentials: true,
    }
    return new Configuration(params)
}

import { Chart } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom'
import { ToolsPageComponent } from './tools-page/tools-page.component'
import { UsersPageComponent } from './users-page/users-page.component'
import { ChangePasswdDlgComponent } from './change-passwd-dlg/change-passwd-dlg.component'
import { LogsPanelComponent } from './logs-panel/logs-panel.component'
Chart.register(zoomPlugin)

@NgModule({
    declarations: [
        AppComponent,
        BranchResultsComponent,
        RunResultsComponent,
        BreadcrumbsComponent,
        MainPageComponent,
        TestCaseResultComponent,
        BranchMgmtComponent,
        RunBoxComponent,
        LocaltimePipe,
        NewFlowComponent,
        NewRunComponent,
        LogBoxComponent,
        NoSanitizePipe,
        ProjectSettingsComponent,
        AgentsPageComponent,
        DiscoveredPageComponent,
        GroupsPageComponent,
        SettingsPageComponent,
        DiagsPageComponent,
        RepoChangesComponent,
        GrpCloudCfgComponent,
        TcrTableComponent,
        FlowAnalysisComponent,
        TabbedPageComponent,
        TabbedPageTabComponent,
        FlowPageComponent,
        FlowChartsComponent,
        BranchStatsComponent,
        ToolsPageComponent,
        UsersPageComponent,
        ChangePasswdDlgComponent,
        LogsPanelComponent,
    ],
    imports: [
        BrowserModule,
        BrowserAnimationsModule,
        HttpClientModule,
        AppRoutingModule,
        FormsModule,
        ReactiveFormsModule,

        // REST API
        ApiModule.forRoot(cfgFactory),

        CodemirrorModule,

        PanelMenuModule,
        MenuModule,
        SplitButtonModule,
        DropdownModule,
        MultiSelectModule,
        TableModule,
        PanelModule,
        TreeModule,
        TreeTableModule,
        ToastModule,
        TabViewModule,
        OrganizationChartModule,
        ChartModule,
        SelectButtonModule,
        DialogModule,
        InputTextModule,
        InputTextareaModule,
        MessageModule,
        MessagesModule,
        ConfirmDialogModule,
        InplaceModule,
        PaginatorModule,
        TabMenuModule,
        CheckboxModule,
        MenubarModule,
        InputSwitchModule,
        InputNumberModule,
        PasswordModule,
        TooltipModule,
        ToggleButtonModule,
        FieldsetModule,
        RadioButtonModule,
        CardModule,
        SliderModule,
        ProgressSpinnerModule,
        ListboxModule,
        DividerModule,
        KeyFilterModule,
    ],
    providers: [
        Title,
        { provide: BASE_PATH, useValue: '/api' },
        BreadcrumbsService,
        MessageService,
        ConfirmationService,
        {
            provide: HTTP_INTERCEPTORS,
            useClass: AuthInterceptor,
            multi: true,
        },
        CookieService,
    ],
    bootstrap: [AppComponent],
})
export class AppModule {}
