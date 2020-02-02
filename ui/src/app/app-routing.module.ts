import { NgModule } from '@angular/core'
import { Routes, RouterModule } from '@angular/router'

// import { AuthGuard } from './auth.guard';
import { MainPageComponent } from './main-page/main-page.component'
import { BranchResultsComponent } from './branch-results/branch-results.component'
import { BranchMgmtComponent } from './branch-mgmt/branch-mgmt.component'
import { RunResultsComponent } from './run-results/run-results.component'
import { TestCaseResultComponent } from './test-case-result/test-case-result.component'
import { FlowResultsComponent } from './flow-results/flow-results.component'
import { NewFlowComponent } from './new-flow/new-flow.component'
import { NewRunComponent } from './new-run/new-run.component'
import { ProjectSettingsComponent } from './project-settings/project-settings.component'
import { ExecutorsPageComponent } from './executors-page/executors-page.component'
import { DiscoveredPageComponent } from './discovered-page/discovered-page.component'
import { GroupsPageComponent } from './groups-page/groups-page.component'

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
        path: 'flows/:id',
        component: FlowResultsComponent,
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
        path: 'executors',
        pathMatch: 'full',
        redirectTo: 'executors/all',
    },
    {
        path: 'executors/:id',
        component: ExecutorsPageComponent,
    },
    {
        path: 'discovered-executors',
        component: DiscoveredPageComponent,
    },
    {
        path: 'executor-groups',
        pathMatch: 'full',
        redirectTo: 'executor-groups/all',
    },
    {
        path: 'executor-groups/:id',
        component: GroupsPageComponent,
    },

    // otherwise redirect to home
    {
        path: '**',
        redirectTo: '',
    },
]

@NgModule({
    imports: [RouterModule.forRoot(routes)],
    exports: [RouterModule],
})
export class AppRoutingModule {}
