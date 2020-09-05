import { async, ComponentFixture, TestBed } from '@angular/core/testing'

import { AgentsPageComponent } from './agents-page.component'

describe('AgentsPageComponent', () => {
    let component: AgentsPageComponent
    let fixture: ComponentFixture<AgentsPageComponent>

    beforeEach(async(() => {
        TestBed.configureTestingModule({
            declarations: [AgentsPageComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(AgentsPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
