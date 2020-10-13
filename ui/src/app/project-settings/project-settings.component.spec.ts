import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { ProjectSettingsComponent } from './project-settings.component'

describe('ProjectSettingsComponent', () => {
    let component: ProjectSettingsComponent
    let fixture: ComponentFixture<ProjectSettingsComponent>

    beforeEach(waitForAsync(() => {
        TestBed.configureTestingModule({
            declarations: [ProjectSettingsComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(ProjectSettingsComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
