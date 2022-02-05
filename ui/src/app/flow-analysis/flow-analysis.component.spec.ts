import { ComponentFixture, TestBed } from '@angular/core/testing'

import { FlowAnalysisComponent } from './flow-analysis.component'

describe('FlowAnalysisComponent', () => {
    let component: FlowAnalysisComponent
    let fixture: ComponentFixture<FlowAnalysisComponent>

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            declarations: [FlowAnalysisComponent],
        }).compileComponents()
    })

    beforeEach(() => {
        fixture = TestBed.createComponent(FlowAnalysisComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
