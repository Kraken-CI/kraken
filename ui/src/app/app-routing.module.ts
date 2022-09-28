import { NgModule } from '@angular/core'
import { Routes, RouterModule } from '@angular/router'

// import { AuthGuard } from './auth.guard';
import { MainPageComponent } from './main-page/main-page.component'
import { BranchResultsComponent } from './branch-results/branch-results.component'
import { BranchMgmtComponent } from './branch-mgmt/branch-mgmt.component'
import { RunResultsComponent } from './run-results/run-results.component'
import { TestCaseResultComponent } from './test-case-result/test-case-result.component'
import { FlowPageComponent } from './flow-page/flow-page.component'
import { NewFlowComponent } from './new-flow/new-flow.component'
import { NewRunComponent } from './new-run/new-run.component'
import { ProjectSettingsComponent } from './project-settings/project-settings.component'
import { AgentsPageComponent } from './agents-page/agents-page.component'
import { DiscoveredPageComponent } from './discovered-page/discovered-page.component'
import { GroupsPageComponent } from './groups-page/groups-page.component'
import { SettingsPageComponent } from './settings-page/settings-page.component'
import { ToolsPageComponent } from './tools-page/tools-page.component'
import { DiagsPageComponent } from './diags-page/diags-page.component'
import { UsersPageComponent } from './users-page/users-page.component'

const routes: Routes = [
    {
        path: '',
        component: MainPageComponent,
        pathMatch: 'full',
        // canActivate: [AuthGuard],
    },
    // {
    //     path: 'login',
    //     component: LoginScreenComponent
    // },
    {
        path: 'branches/:id',
        component: BranchMgmtComponent,
    },
    {
        path: 'branches/:id/:kind',
        component: BranchResultsComponent,
    },
    {
        path: 'branches/:id/:kind/flows/new',
        component: NewFlowComponent,
    },
    {
        path: 'flows/:flow_id/stages/:stage_id/new',
        component: NewRunComponent,
    },
    {
        path: 'flows/:id/:tab',
        component: FlowPageComponent,
    },
    {
        path: 'flows/:id',
        component: FlowPageComponent,
    },
    {
        path: 'runs/:id',
        redirectTo: 'runs/:id/',
    },
    {
        path: 'runs/:id/:tab',
        component: RunResultsComponent,
    },
    {
        path: 'test_case_results/:id',
        component: TestCaseResultComponent,
    },
    {
        path: 'projects/:id',
        component: ProjectSettingsComponent,
    },
    {
        path: 'agents',
        pathMatch: 'full',
        redirectTo: 'agents/all',
    },
    {
        path: 'agents/:id',
        component: AgentsPageComponent,
    },
    {
        path: 'discovered-agents',
        component: DiscoveredPageComponent,
    },
    {
        path: 'agents-groups',
        pathMatch: 'full',
        redirectTo: 'agents-groups/all',
    },
    {
        path: 'agents-groups/:id',
        component: GroupsPageComponent,
    },
    {
        path: 'settings',
        component: SettingsPageComponent,
    },
    {
        path: 'tools',
        component: ToolsPageComponent,
    },
    {
        path: 'diagnostics/:tab',
        component: DiagsPageComponent,
    },
    {
        path: 'users',
        component: UsersPageComponent,
    },

    // otherwise redirect to home
    {
        path: '**',
        redirectTo: '',
    },
]

@NgModule({
    imports: [
        RouterModule.forRoot(routes, { relativeLinkResolution: 'legacy' }),
    ],
    exports: [RouterModule],
})
export class AppRoutingModule {}
